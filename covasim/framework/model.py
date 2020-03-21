'''
This file contains all the code for a single run of Covid-ABM.

Based heavily on LEMOD-FP (https://github.com/amath-idm/lemod_fp).
'''

#%% Imports
import datetime as dt
import numpy as np # Needed for a few things not provided by pl
import sciris as sc
from . import utils as cov_ut

# Specify all externally visible functions this file defines
__all__ = ['ParsObj', 'Result', 'Person', 'Sim', 'single_run', 'multi_run']



#%% Define classes
class ParsObj(sc.prettyobj):
    '''
    A class based around performing operations on a self.pars dict.
    '''

    def __init__(self, pars):
        self.update_pars(pars, create=True)
        return

    def __getitem__(self, key):
        ''' Allow sim['par_name'] instead of sim.pars['par_name'] '''
        return self.pars[key]

    def __setitem__(self, key, value):
        ''' Ditto '''
        if key in self.pars:
            self.pars[key] = value
        else:
            suggestion = sc.suggest(key, self.pars.keys())
            if suggestion:
                errormsg = f'Key {key} not found; did you mean "{suggestion}"?'
            else:
                all_keys = '\n'.join(list(self.pars.keys()))
                errormsg = f'Key {key} not found; available keys:\n{all_keys}'
            raise KeyError(errormsg)
        return

    def update_pars(self, pars, create=False):
        '''
        Update internal dict with new pars. If create is False, then raise a KeyError
        if the key does not already exist.
        '''
        if not isinstance(pars, dict):
            raise TypeError(f'The pars object must be a dict; you supplied a {type(pars)}')
        if not hasattr(self, 'pars'):
            self.pars = pars
        elif pars is not None:
            if not create:
                available_keys = list(self.pars.keys())
                mismatches = [key for key in pars.keys() if key not in available_keys]
                if len(mismatches):
                    errormsg = f'Key(s) {mismatches} not found; available keys are {available_keys}'
                    raise KeyError(errormsg)
            self.pars.update(pars)
        return



class Result(sc.prettyobj):
    '''
    Stores a single result -- by default, acts like an array.

    Example:
        import covasim as cova
        r1 = cova.Result(name='test1', npts=10)
        r1[:5] = 20
        print(r2.values)
        r2 = cova.Result(name='test2', values=range(10))
        print(r2)
    '''
    def __init__(self, name=None, values=None, npts=None, scale=True, ispercentage=False):
        self.name = name  # Name of this result
        self.ispercentage = ispercentage  # Whether or not the result is a percentage
        self.scale = scale  # Whether or not to scale the result by the scale factor
        if values is None:
            if npts is not None:
                values = np.zeros(int(npts)) # If length is known, use zeros
            else:
                values = [] # Otherwise, empty
        self.values = np.array(values, dtype=float) # Ensure it's an array
        return

    def __getitem__(self, *args, **kwargs):
        return self.values.__getitem__(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        return self.values.__setitem__(*args, **kwargs)

    @property
    def npts(self):
        return len(self.values)


class Person(sc.prettyobj):
    '''
    Class for a single person.
    '''
    def __init__(self, *args, **kwargs):
        raise NotImplementedError



class Sim(ParsObj):
    '''
    The Sim class handles the running of the simulation: the number of people,
    number of time points, and the parameters of the simulation.
    '''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) # Initialize and set the parameters as attributes
        return

    def set_seed(self, seed: int = None, randomize: bool = False) -> None:
        """
        Set the seed for the random number stream

        Examples:

            >>> sim.set_seed(324) # Set sim['seed'] to 324 and reset the number stream

            >>> sim.set_seed() # Using sim['seed'], reset the number stream

            >>> sim.set_seed(randomize=True) # Randomize the number stream (no seed)

        Args:
            seed (int): Optional. Set seed and reset the random number stream.
            randomize (bool): Optional. If True, randomly select seed

        Returns:
            None

        """

        if randomize:
            if seed is None:
                seed = None
            else:
                raise ValueError('You can supply a seed or set randomize=True, but not both')
        else:
            if seed is None:
                seed = self['seed'] # Use the stored seed
            else:
                self['seed'] = seed # Store the supplied seed
        cov_ut.set_seed(seed)
        return

    @property
    def n(self):
        ''' Count the number of people '''
        return len(self.people)

    @property
    def npts(self):
        ''' Count the number of time points '''
        return int(self['n_days'] + 1)

    @property
    def tvec(self):
        ''' Create a time vector '''
        return np.arange(self['n_days'] + 1)


    def inds2dates(self, inds, dateformat=None):
        ''' Convert a set of indices to a set of dates '''

        if sc.isnumber(inds): # If it's a number, convert it to a list
            inds = sc.promotetolist(inds)

        if dateformat is None:
            dateformat = '%b-%d'

        dates = []
        for ind in inds:
            tmp = self['start_day'] + dt.timedelta(days=int(ind))
            dates.append(tmp.strftime(dateformat))
        return dates


    def get_person(self, ind):
        ''' Return a person based on their ID '''
        return self.people[self.uids[ind]]


    def init_results(self):
        ''' Initialize results '''
        raise NotImplementedError


    def init_people(self):
        ''' Create the people '''
        raise NotImplementedError


    def summary_stats(self):
        ''' Compute the summary statistics to display at the end of a run '''
        raise NotImplementedError


    def run(self):
        ''' Run the simulation '''
        raise NotImplementedError


    def likelihood(self):
        '''
        Compute the log-likelihood of the current simulation based on the number
        of new diagnoses.
        '''
        raise NotImplementedError


    def _make_resdict(self, for_json=True):
        ''' Pre-convert the results structure to a friendier output'''
        resdict = {}
        if for_json:
            resdict['timeseries_keys'] = self.reskeys
        for key,res in self.results.items():
            if isinstance(res, Result):
                res = res.values
            if for_json or sc.isiterable(res) and len(res)==self.npts:
                resdict[key] = res
        return resdict


    def to_json(self, filename=None, tostring=True, indent=2, *args, **kwargs):
        """
        Export results as JSON.

        Args:
            filename (str): if None, return string; else, write to file

        Returns:
            A unicode string containing a JSON representation of the results,
            or writes the JSON file to disk

        """
        resdict = self._make_resdict()

        if filename is None:
            output = sc.jsonify(resdict, tostring=tostring, indent=indent, *args, **kwargs)
        else:
            output = sc.savejson(filename=filename, obj=resdict, *args, **kwargs)

        return output


    def to_xlsx(self, filename=None):
        """
        Export results as XLSX

        Args:
            filename (str): if None, return string; else, write to file

        Returns:
            An sc.Spreadsheet with an Excel file, or writes the file to disk

        """
        resdict = self._make_resdict(for_json=False)
        df = sc.dataframe(resdict).pandas()
        df.index = self.tvec
        df.index.name = 'Day'

        spreadsheet = sc.Spreadsheet()
        spreadsheet.freshbytes()
        df.to_excel(spreadsheet.bytes, engine='xlsxwriter')
        spreadsheet.load()

        if filename is None:
            output = spreadsheet
        else:
            output = spreadsheet.save(filename)

        return output

    def plot(self):
        '''
        Plot the results -- can supply arguments for both the figure and the plots.
        '''
        raise NotImplementedError


    def plot_people(self):
        ''' Use imshow() to show all individuals as rows, with time as columns, one pixel per timestep per person '''
        raise NotImplementedError


def single_run(sim, ind=0, noise=0.0, noisepar=None, verbose=None, sim_args=None, **kwargs):
    '''
    Convenience function to perform a single simulation run. Mostly used for
    parallelization, but can also be used directly:
        import covasim.cova_generic as cova
        sim = cova.Sim() # Create a default simulation
        sim = cova.single_run(sim) # Run it, equivalent(ish) to sim.run()
    '''

    if sim_args is None:
        sim_args = {}

    new_sim = sc.dcp(sim) # To avoid overwriting it; otherwise, use

    if verbose is None:
        verbose = new_sim['verbose']

    new_sim['seed'] += ind # Reset the seed, otherwise no point of parallel runs
    new_sim.set_seed()

    # If the noise parameter is not found, guess what it should be
    if noisepar is None:
        guesses = ['r_contact', 'r0', 'beta']
        found = [guess for guess in guesses if guess in sim.pars.keys()]
        if len(found)!=1:
            raise KeyError(f'Cound not guess noise parameter since out of {guesses}, {found} were found')
        else:
            noisepar = found[0]

    # Handle noise -- normally distributed fractional error
    noiseval = noise*np.random.normal()
    if noiseval > 0:
        noisefactor = 1 + noiseval
    else:
        noisefactor = 1/(1-noiseval)
    new_sim[noisepar] *= noisefactor

    if verbose>=1:
        print(f'Running a simulation using {new_sim["seed"]} seed and {noisefactor} noise')

    # Handle additional arguments
    for key,val in kwargs.items():
        print(f'Processing {key}:{val}')
        if key in new_sim.pars.keys():
            if verbose>=1:
                print(f'Setting key {key} from {new_sim[key]} to {val}')
                new_sim[key] = val
            pass
        else:
            raise KeyError(f'Could not set key {key}: not a valid parameter name')

    # Run
    new_sim.run(verbose=verbose)

    return new_sim


def multi_run(sim, n=4, noise=0.0, noisepar=None, iterpars=None, verbose=None, sim_args=None, combine=False, **kwargs):
    '''
    For running multiple runs in parallel. Example:
        import covid_seattle
        sim = covid_seattle.Sim()
        sims = covid_seattle.multi_run(sim, n=6, noise=0.2)
    '''

    # Create the sims
    if sim_args is None:
        sim_args = {}

    # Handle iterpars
    if iterpars is None:
        iterpars = {}
    else:
        n = None # Reset and get from length of dict instead
        for key,val in iterpars.items():
            new_n = len(val)
            if n is not None and new_n != n:
                raise ValueError(f'Each entry in iterpars must have the same length, not {n} and {len(val)}')
            else:
                n = new_n

    # Copy the simulations
    iterkwargs = {'ind':np.arange(n)}
    iterkwargs.update(iterpars)
    kwargs = {'sim':sim, 'noise':noise, 'noisepar':noisepar, 'verbose':verbose, 'sim_args':sim_args}
    sims = sc.parallelize(single_run, iterkwargs=iterkwargs, kwargs=kwargs)

    if not combine:
        output = sims
    else:
        print('WARNING: not tested!')
        output_sim = sc.dcp(sims[0])
        output_sim.pars['parallelized'] = n # Store how this was parallelized
        output_sim.pars['n'] *= n # Restore this since used in later calculations -- a bit hacky, it's true
        for sim in sims[1:]: # Skip the first one
            output_sim.people.update(sim.people)
            for key in sim.results_keys:
                output_sim.results[key] += sim.results[key]
        output = output_sim

    return output
