# Paraphrase corpus review sheet (Gate C)

- corpus version: `v1`
- generator: `soofi-s-isar-preview` · judge: `soofi-s-isar-preview`
- sha256: `68037cb747a84cde5375af71e6680ef6a8aa8adfc9fa441cc7bfa41a2714ad66`
- sample: 125 variants

For each item, mark **equivalent** or **not equivalent**: does the rewrite demand exactly the same function (or class) as the original? Wording, tone and the order of requirements are not differences in meaning.

| # | verdict (fill in) | note |
|---|---|---|
| 1 | equivalent (minor) | 'write to output' becomes 'to an I/O stream' |
| 2 | equivalent (minor) | param/return glosses shortened |
| 3 | not equivalent | add_arrow Returns: original is a list '[line,arrow_head,text]'; rewrite says 'A tuple containing the line, arrow head, and text objects' |
| 4 | equivalent |  |
| 5 | equivalent |  |
| 6 | equivalent |  |
| 7 | equivalent |  |
| 8 | equivalent (minor) | disk element: drops 'neighborhood is 1, 0 otherwise' |
| 9 | equivalent |  |
| 10 | not equivalent | get_server: ValueError no longer says when it is raised (original: if the server is not found) |
| 11 | equivalent |  |
| 12 | equivalent |  |
| 13 | equivalent |  |
| 14 | equivalent |  |
| 15 | equivalent |  |
| 16 | equivalent (minor) | compiler/connection sentence is a garbled run-on but keeps all facts |
| 17 | equivalent (minor) | awkward wording for the private constructor |
| 18 | equivalent |  |
| 19 | equivalent |  |
| 20 | equivalent |  |
| 21 | equivalent (minor) | 'use only in a transformer' becomes the stronger 'must only be used' |
| 22 | equivalent |  |
| 23 | equivalent |  |
| 24 | equivalent |  |
| 25 | equivalent |  |
| 26 | equivalent |  |
| 27 | equivalent |  |
| 28 | equivalent (minor) | ancestor ordering garbled ('earliest, most recent'); the original is itself contradictory |
| 29 | equivalent |  |
| 30 | equivalent |  |
| 31 | equivalent |  |
| 32 | equivalent |  |
| 33 | equivalent |  |
| 34 | equivalent |  |
| 35 | equivalent |  |
| 36 | equivalent |  |
| 37 | equivalent |  |
| 38 | equivalent |  |
| 39 | equivalent |  |
| 40 | equivalent (minor) | 'same size as the first input (or a single NaN)' becomes 'matching the dimensionality' |
| 41 | equivalent |  |
| 42 | equivalent |  |
| 43 | equivalent |  |
| 44 | equivalent (minor) | 'Matched' becomes 'Aligned' in the class title |
| 45 | equivalent |  |
| 46 | equivalent |  |
| 47 | equivalent (minor) | drops the motivation prose; keeps examples and defaults |
| 48 | equivalent |  |
| 49 | equivalent |  |
| 50 | equivalent |  |
| 51 | equivalent |  |
| 52 | equivalent (minor) | 'frequency to enforce' becomes 'loop frequency' |
| 53 | equivalent |  |
| 54 | equivalent |  |
| 55 | equivalent |  |
| 56 | equivalent |  |
| 57 | equivalent |  |
| 58 | equivalent |  |
| 59 | equivalent |  |
| 60 | equivalent (minor) | adds 'dictionary-based' |
| 61 | equivalent |  |
| 62 | equivalent |  |
| 63 | equivalent |  |
| 64 | equivalent |  |
| 65 | equivalent |  |
| 66 | equivalent (minor) | 'list of actions' becomes 'queue' while the methods still say stack and last-added first |
| 67 | equivalent |  |
| 68 | equivalent (minor) | adds 'in seconds' to the flush timeout |
| 69 | equivalent | translated from Chinese to English |
| 70 | equivalent (minor) | adds 'top-left corner' for fill_rect |
| 71 | equivalent |  |
| 72 | equivalent |  |
| 73 | equivalent (minor) | adds a condition to :raises: CompletionError |
| 74 | equivalent |  |
| 75 | equivalent (minor) | very terse: param descriptions reduced to one or two words |
| 76 | equivalent |  |
| 77 | equivalent |  |
| 78 | not equivalent | drops the stated return form '(target_id, is_group)': says the target information is extracted, not that a (target_id, is_group) tuple is returned |
| 79 | equivalent |  |
| 80 | equivalent |  |
| 81 | equivalent |  |
| 82 | equivalent (minor) | drops '(+ data)' |
| 83 | equivalent |  |
| 84 | equivalent |  |
| 85 | equivalent |  |
| 86 | equivalent | translated from Chinese to English |
| 87 | equivalent |  |
| 88 | equivalent |  |
| 89 | equivalent |  |
| 90 | equivalent (minor) | adds 'triangular' |
| 91 | equivalent |  |
| 92 | equivalent (minor) | 'True if writable, False otherwise' becomes 'writable flag' |
| 93 | equivalent |  |
| 94 | equivalent |  |
| 95 | equivalent |  |
| 96 | equivalent (minor) | run_and_wait: no longer says it starts the task and returns the result |
| 97 | equivalent |  |
| 98 | equivalent |  |
| 99 | equivalent | translated from Chinese to English |
| 100 | equivalent |  |
| 101 | equivalent |  |
| 102 | equivalent (minor) | translated from Chinese; adds what _replace_table_block returns |
| 103 | equivalent |  |
| 104 | equivalent (minor) | drops the verb 'Display' |
| 105 | equivalent |  |
| 106 | equivalent |  |
| 107 | equivalent |  |
| 108 | equivalent (minor) | adds debug-friendly (repr) and user-facing (str) |
| 109 | not equivalent | shingling_from_mol Returns: adds 'shingling set' (original: 'The molecular shingling', and elsewhere 'a list of n-grams') |
| 110 | equivalent |  |
| 111 | equivalent |  |
| 112 | not equivalent | drops the default values the class docstring lists (export_dir '', linker_file None, target '', empty list/dict values); keeps only the key meanings |
| 113 | equivalent |  |
| 114 | equivalent (minor) | 'exact display name'; limit described as a threshold |
| 115 | equivalent (minor) | names __new__/__init__ and the base-class return explicitly |
| 116 | equivalent |  |
| 117 | equivalent |  |
| 118 | equivalent (minor) | 'Prevent mutability' becomes 'Prevent any changes to attributes' |
| 119 | equivalent (minor) | fill_rect: drops 'outline and interior' |
| 120 | equivalent |  |
| 121 | equivalent (minor) | key described as a string |
| 122 | equivalent |  |
| 123 | equivalent |  |
| 124 | equivalent |  |
| 125 | equivalent |  |

---

## 1. RealClassEval/csn/snippet_210 — `llm_formal_01` (formal)

**Original**

```python

class EnumDefinition:
    '''Prototype of a enum.'''

    def __init__(self, name: str, values: list[str]):
        '''Initialize enum definition with a name and possible values.'''
        pass

    def writeDefinition(self, target: IO[str], ind: str, common_namespace: str) -> None:
        '''Write enum definition to output.'''
        pass
```

**Rewrite**

```python

class EnumDefinition:
    '''A prototype for an enumeration definition.'''

    def __init__(self, name: str, values: list[str]):
        '''The enumeration definition is initialized with a name and a list of possible values.'''
        pass

    def writeDefinition(self, target: IO[str], ind: str, common_namespace: str) -> None:
        '''The enumeration definition is written to an I/O stream.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing and minor clarifications (e.g., "enumeration" instead of "enum", explicit "list" mention) without altering requirements, types, or behavior._

---

## 2. RealClassEval/csn/snippet_206 — `llm_formal_01` (formal)

**Original**

```python
class StreamCodeDebug:
    '''
    Codes utility methods
    '''
    @staticmethod
    def op_id(op_id):
        '''
        Returns the name of the given OP Code
        :param op_id: OP Code
        :return: Name of the OP Code
        '''
        pass
    @staticmethod
    def type_code(type_id):
        '''
        Returns the name of the given Type Code
        :param type_id: Type code
        :return: Name of the type code
        '''
        pass
    @staticmethod
    def flags(flags):
        '''
        Returns the names of the class description flags found in the given
        integer
        :param flags: A class description flag entry
        :return: The flags names as a single string
        '''
        pass
```

**Rewrite**

```python
class StreamCodeDebug:
    '''
    Provides utility methods for code representation interpretation.
    '''
    @staticmethod
    def op_id(op_id):
        '''
        The operation code name is returned for the parameter op_id.
        '''
        pass
    @staticmethod
    def type_code(type_id):
        '''
        The type code name is returned for the parameter type_id.
        '''
        pass
    @staticmethod
    def flags(flags):
        '''
        The names of the class description flags present in the parameter flags are returned as a single string.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases the docstrings with synonymous language without changing requirements, types, or behavior._

---

## 3. RealClassEval/csn/snippet_271 — `llm_lexical_01` (lexical)

**Original**

```python

class Subplot:
    '''Subplot containing WMEL.'''

    def __init__(self, ax, energies, number_of_interactions=4, title='', title_font_size=16, state_names=None, virtual=[None], state_font_size=14, state_text_buffer=0.5, label_side='left'):
        '''Subplot.
        Parameters
        ----------
        ax : matplotlib axis
            The axis.
        energies : 1D array-like
            Energies (scaled between 0 and 1)
        number_of_interactions : integer
            Number of interactions in diagram.
        title : string (optional)
            Title of subplot. Default is empty string.
        state_names: list of str (optional)
            list of the names of the states
        virtual: list of ints (optional)
            list of indexes of any vitual energy states
        state_font_size: numtype (optional)
            font size for the state lables
        state_text_buffer: numtype (optional)
            space between the energy level bars and the state labels
        '''
        pass

    def add_arrow(self, index, between, kind, label='', head_length=10, head_aspect=1, font_size=14, color='k'):
        '''Add an arrow to the WMEL diagram.
        Parameters
        ----------
        index : integer
            The interaction, or start and stop interaction for the arrow.
        between : 2-element iterable of integers
            The inital and final state of the arrow
        kind : {'ket', 'bra', 'outbra', 'outket'}
            The kind of interaction.
        label : string (optional)
            Interaction label. Default is empty string.
        head_length: number (optional)
            size of arrow head
        font_size : number (optional)
            Label font size. Default is 14.
        color : matplotlib color (optional)
            Arrow color. Default is black.
        Returns
        -------
        [line,arrow_head,text]
        '''
        pass
```

**Rewrite**

```python

class Subplot:
    '''A subplot incorporating WMEL.'''

    def __init__(self, ax, energies, number_of_interactions=4, title='', title_font_size=16, state_names=None, virtual=[None], state_font_size=14, state_text_buffer=0.5, label_side='left'):
        '''Creates a new Subplot instance.
        Parameters
        ----------
        ax : matplotlib axis
            The matplotlib axis to render on.
        energies : 1D array-like
            Energy values scaled between 0 and 1.
        number_of_interactions : integer
            Count of interactions depicted in the diagram.
        title : string (optional)
            Subplot title; defaults to empty string.
        state_names : list of str (optional)
            Labels assigned to each state.
        virtual : list of ints (optional)
            Indices identifying virtual energy states.
        state_font_size : numtype (optional)
            Font size applied to state label text.
        state_text_buffer : numtype (optional)
            Gap separating energy bars from state labels.
        '''
        pass

    def add_arrow(self, index, between, kind, label='', head_length=10, head_aspect=1, font_size=14, color='k'):
        '''Adds an arrow to the WMEL diagram.
        Parameters
        ----------
        index : integer
            Single interaction index or pair defining start and end interactions.
        between : 2-element iterable of integers
            Starting and ending state indices for the arrow.
        kind : {'ket', 'bra', 'outbra', 'outket'}
            Interaction direction category.
        label : string (optional)
            Optional text annotation for the interaction.
        head_length: number (optional)
            Arrowhead dimension.
        font_size : number (optional)
            Label text size; defaults to 14.
        color : matplotlib color (optional)
            Arrow color; defaults to black.
        Returns
        -------
        A tuple containing the line, arrow head, and text objects.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses different wording and register but preserves all parameter meanings, types, and behavioral requirements without adding, dropping, or altering any specifications._

---

## 4. RealClassEval/post_cut-off/snippet_340 — `llm_formal_01` (formal)

**Original**

```python
class Fix:
    '''Class representing a fixed state variable in the optimization problem.
    A fixed state variable is one that is constrained to a specific value
    and cannot be optimized.
    Attributes:
        value: The fixed value that the state variable must take.
    '''

    def __init__(self, value):
        '''Initialize a new fixed state variable.
        Args:
            value: The fixed value that the state variable must take.
        '''
        pass

    def __repr__(self):
        '''Get a string representation of this fixed state variable.
        Returns:
            str: A string representation showing the fixed value.
        '''
        pass
```

**Rewrite**

```python
class Fix:
    '''A fixed state variable in an optimization problem is defined as a state variable constrained to a specific value and incapable of optimization.
    Attributes:
        value: The specific value to which the state variable is constrained.
    '''

    def __init__(self, value):
        '''A new instance of Fix is created for an optimization problem, fixing the state variable to a specific value that is not subject to optimization.
        Args:
            value: The specific value to which the state variable is constrained.
        '''
        pass

    def __repr__(self):
        '''A string representation of the fixed state variable instance is returned by the method.
        Returns:
            str: A string that displays the fixed value of the state variable.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses more verbose phrasing but preserves all original requirements about the fixed state variable's definition, attribute, and behavior without adding, dropping, or altering any constraints._

---

## 5. RealClassEval/csn/snippet_98 — `llm_formal_01` (formal)

**Original**

```python
class LCModel:
    '''
        base class for simple learning curve models
            '''

    def fit(self, times, losses, configs=None):
        '''
            function to train the model on the observed data
            Parameters:
            -----------
            times: list
                list of numpy arrays of the timesteps for each curve
            losses: list
                list of numpy arrays of the loss (the actual learning curve)
            configs: list or None
                list of the configurations for each sample. Each element
                has to be a numpy array. Set to None, if no configuration
                information is available.
        '''
        pass

    def predict_unseen(self, times, config):
        '''
            predict the loss of an unseen configuration
            Parameters:
            -----------
            times: numpy array
                times where to predict the loss
            config: numpy array
                the numerical representation of the config
            Returns:
            --------
            mean and variance prediction at input times for the given config
        '''
        pass

    def extend_partial(self, times, obs_times, obs_losses, config=None):
        '''
            extends a partially observed curve
            Parameters:
            -----------
            times: numpy array
                times where to predict the loss
            obs_times: numpy array
                times where the curve has already been observed
            obs_losses: numpy array
                corresponding observed losses
            config: numpy array
                numerical reperesentation of the config; None if no config
                information is available
            Returns:
            --------
            mean and variance prediction at input times

        '''
        pass
```

**Rewrite**

```python
class LCModel:
    '''
        This class defines the base type for simple learning curve models.
            '''

    def fit(self, times, losses, configs=None):
        '''
            The model is trained using the observed data provided in the method call.
        Parameters:
        -----------
        times: list
            A list of numpy arrays containing the timesteps for each learning curve.
        losses: list
            A list of numpy arrays containing the loss values representing the actual learning curves.
        configs: list or None
            A list of numpy arrays representing the configuration parameters for each sample. If configuration information is unavailable, this parameter must be set to None.
        '''
        pass

    def predict_unseen(self, times, config):
        '''
            The loss for an unseen configuration is predicted given specific input times.
        Parameters:
        -----------
        times: numpy array
            A numpy array specifying the times at which to predict the loss.
        config: numpy array
            A numpy array representing the numerical configuration for prediction.
        Returns:
        --------
        The mean and variance of the predicted loss at the specified input times for the given configuration.
        '''
        pass

    def extend_partial(self, times, obs_times, obs_losses, config=None):
        '''
            A partially observed learning curve is extended to predict loss at new times.
        Parameters:
        -----------
        times: numpy array
            A numpy array specifying the times at which to predict the loss.
        obs_times: numpy array
            A numpy array containing the times at which loss values have been observed.
        obs_losses: numpy array
            A numpy array containing the corresponding observed loss values.
        config: numpy array or None
            A numpy array representing the numerical configuration. If configuration information is unavailable, this parameter must be set to None.
        Returns:
        --------
        The mean and variance of the predicted loss at the specified input times.

        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings describe identical parameter requirements, return value semantics, and behavioral conditions without altering types, meanings, or constraints._

---

## 6. RealClassEval/csn/snippet_258 — `llm_formal_01` (formal)

**Original**

```python

class RGsolution:
    '''Class representing a continuous (interpolated) solution to the
    SMEFT RGEs to be used for plotting.'''

    def __init__(self, fun, scale_min, scale_max):
        '''Initialize.
        Parameters:
        - fun: function of the scale that is expected to return a
        dictionary with the RGE solution and to accept vectorized input.
        - scale_min, scale_max: lower and upper boundaries of the scale
        '''
        pass

    def plotdata(self, key, part='re', scale='log', steps=50):
        '''Return a tuple of arrays x, y that can be fed to plt.plot,
        where x is the scale in GeV and y is the parameter of interest.
        Parameters:
        - key: dicionary key of the parameter to be plotted (e.g. a WCxf
          coefficient name or a SM parameter like 'g')
        - part: plot the real part 're' (default) or the imaginary part 'im'
        - scale: 'log'; make the x steps logarithmically distributed; for
          'linear', linearly distributed
        - steps: steps in x to take (default: 50)
        '''
        pass

    def plotdata(self, key, part='re', scale='log', steps=50):
        '''Plot the RG evolution of parameter `key`.
        Parameters:
        - part, scale, steps: see `plotdata`
        - legend: boolean, show the legend (default: True)
        - plotargs: dictionary of arguments to be passed to plt.plot
        '''
        pass
```

**Rewrite**

```python

class RGsolution:
    '''Represents a continuous interpolated solution to the renormalization group equations of the Standard Model Effective Field Theory for plot generation.'''

    def __init__(self, fun, scale_min, scale_max):
        '''Initializes the instance.
        The argument 'fun' must be a function that accepts vectorized scale input and returns a dictionary containing the renormalization group equation solution.
        The arguments 'scale_min' and 'scale_max' specify the lower and upper boundaries of the scale range.
        '''
        pass

    def plotdata(self, key, part='re', scale='log', steps=50):
        '''Returns a tuple (x, y) of arrays that are valid inputs for the matplotlib.pyplot.plot function.
        The array x contains the renormalization group scale values expressed in gigaelectronvolts (GeV).
        The array y contains the values of the parameter specified by 'key'.
        The parameter 'key' is a dictionary key for accessing the parameter of interest from the solution data.
        The parameter 'part' selects the component to plot: 're' for real part or 'im' for imaginary part.
        The parameter 'scale' determines the x-axis scaling distribution: 'log' for logarithmic or 'linear' for linear.
        The parameter 'steps' defines the number of intermediate sampling points along the scale axis, defaulting to 50.
        '''
        pass

    def plotdata(self, key, part='re', scale='log', steps=50):
        '''Generates a plot of the renormalization group evolution for the parameter specified by 'key'.
        The parameters 'part', 'scale', and 'steps' are configured according to the specifications of the 'plotdata' method.
        The parameter 'legend' is a boolean controlling visibility of the plot legend, defaulting to True.
        The parameter 'plotargs' is a dictionary of additional keyword arguments passed to the matplotlib.pyplot.plot function.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification elaborates on technical terms (e.g., spelling out "renormalization group equations" and "gigaelectronvolts") and adds minor clarifications (e.g., "additional keyword arguments") without altering the core requirements, parameter meanings, return values, or behavior for any_

---

## 7. RealClassEval/post_cut-off/snippet_150 — `llm_lexical_01` (lexical)

**Original**

```python
@dataclass
class BudgetTracker:
    '''
    Tracks agent spending and budget decisions.
    Provides comprehensive budget management including affordability checks,
    spending tracking per agent card, and cost analysis over time.
    '''

    def can_afford(self, cost: Decimal) -> bool:
        '''Check if the agent can afford a given cost.'''
        pass

    def spend(self, amount: Decimal, agent_card_name: str) -> None:
        '''Record a spending transaction and update budget tracking.'''
        pass
```

**Rewrite**

```python
@dataclass
class BudgetTracker:
    '''
    Monitors agent expenditures and budgetary decisions.
    Delivers thorough budget management featuring cost affordability assessments,
    expenditure recording for each agent card, and analysis of costs over time.
    '''

    def can_afford(self, cost: Decimal) -> bool:
        '''Determine if the agent has adequate funds to cover a specified cost.'''
        pass

    def spend(self, amount: Decimal, agent_card_name: str) -> None:
        '''Log a spending transaction and synchronize the budget tracking data.'''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing (e.g., "monitors" vs "tracks", "expenditures" vs "spending", "assessments" vs "checks") without altering any functional requirements, types, or behavioral expectations._

---

## 8. RealClassEval/csn/snippet_58 — `llm_terse_01` (terse)

**Original**

```python

class MorphologicalStructFactory:
    '''
    Factory methods for generating morphological structuring elements
    '''
    @staticmethod
    def get_disk(radius: int) -> np.ndarray:
        '''
        :param radius: Radius of disk
        :return: The structuring element where elements of the neighborhood are 1 and 0 otherwise.
        '''
        pass
    @staticmethod
    def get_rectangle(width: int, height: int) -> np.ndarray:
        '''
        :param width: Width of rectangle
        :param height: Height of rectangle
        :return: A structuring element consisting only of ones, i.e. every pixel belongs to the neighborhood.
        '''
        pass
    @staticmethod
    def get_square(width: int) -> np.ndarray:
        '''
        :param width: Size of square
        :return: A structuring element consisting only of ones, i.e. every pixel belongs to the neighborhood.
        '''
        pass
```

**Rewrite**

```python

class MorphologicalStructFactory:
    '''
    Morphological structuring element factory
    '''
    @staticmethod
    def get_disk(radius: int) -> np.ndarray:
        '''
        :param radius: Disk radius
        :return: Disk structuring element
        '''
        pass
    @staticmethod
    def get_rectangle(width: int, height: int) -> np.ndarray:
        '''
        :param width: Rectangle width
        :param height: Rectangle height
        :return: All-ones structuring element
        '''
        pass
    @staticmethod
    def get_square(width: int) -> np.ndarray:
        '''
        :param width: Square size
        :return: All-ones structuring element
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses standard morphological terminology (e.g., "Disk structuring element" and "All-ones structuring element") that precisely conveys the same binary pattern requirements as the original docstrings without altering specifications._

---

## 9. RealClassEval/csn/snippet_51 — `llm_lexical_01` (lexical)

**Original**

```python

class Array:
    '''Use a Struct as a callable to unpack a bunch of bytes as a list.'''

    def __init__(self, fmt):
        '''Initialize the Struct unpacker.'''
        pass

    def __call__(self, buf):
        '''Perform the actual unpacking.'''
        pass
```

**Rewrite**

```python

class Array:
    '''Employ a Struct instance as a callable to unpack a bytes sequence into a list.'''

    def __init__(self, fmt):
        '''Set up the Struct unpacker.'''
        pass

    def __call__(self, buf):
        '''Carry out the actual unpacking.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing without changing the technical requirements or behavior described in the original._

---

## 10. RealClassEval/post_cut-off/snippet_363 — `llm_terse_01` (terse)

**Original**

```python

class SimpleRegistryClient:
    '''Simple client for querying MCP registries for server discovery.'''

    def __init__(self, registry_url: Optional[str]=None):
        '''Initialize the registry client.
        Args:
            registry_url (str, optional): URL of the MCP registry.
                If not provided, uses the MCP_REGISTRY_URL environment variable
                or falls back to the default demo registry.
        '''
        pass

    def list_servers(self, limit: int=100, cursor: Optional[str]=None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        '''List all available servers in the registry.
        Args:
            limit (int, optional): Maximum number of entries to return. Defaults to 100.
            cursor (str, optional): Pagination cursor for retrieving next set of results.
        Returns:
            Tuple[List[Dict[str, Any]], Optional[str]]: List of server metadata dictionaries and the next cursor if available.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def search_servers(self, query: str) -> List[Dict[str, Any]]:
        '''Search for servers in the registry.
        Args:
            query (str): Search query string.
        Returns:
            List[Dict[str, Any]]: List of matching server metadata dictionaries.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def get_server_info(self, server_id: str) -> Dict[str, Any]:
        '''Get detailed information about a specific server.
        Args:
            server_id (str): ID of the server.
        Returns:
            Dict[str, Any]: Server metadata dictionary.
        Raises:
            requests.RequestException: If the request fails.
            ValueError: If the server is not found.
        '''
        pass

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        '''Find a server by its name.
        Args:
            name (str): Name of the server to find.
        Returns:
            Optional[Dict[str, Any]]: Server metadata dictionary or None if not found.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def find_server_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        '''Find a server by exact name match or server ID.
        This is a simple, efficient lookup that only makes network requests when necessary:
        1. Server ID (UUID format) - direct API call
        2. Exact name match from server list - single additional API call
        Args:
            reference (str): Server reference (ID or exact name).
        Returns:
            Optional[Dict[str, Any]]: Server metadata dictionary or None if not found.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass
```

**Rewrite**

```python

class SimpleRegistryClient:
    '''MCP registry client for server discovery'''

    def __init__(self, registry_url: Optional[str]=None):
        '''Initialize MCP registry client.
        Args:
            registry_url: Optional MCP registry URL from MCP_REGISTRY_URL env or demo registry.
        '''
        pass

    def list_servers(self, limit: int=100, cursor: Optional[str]=None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        '''List servers.
        Args:
            limit: Max servers (default 100)
            cursor: Pagination cursor
        Returns:
            Tuple[List[Dict[str, Any]], Optional[str]]: Server metadata list and next cursor
        Raises:
            requests.RequestException
        '''
        pass

    def search_servers(self, query: str) -> List[Dict[str, Any]]:
        '''Search servers by query.
        Args:
            query: Search string
        Returns:
            List[Dict[str, Any]]: Matching server metadata list
        Raises:
            requests.RequestException
        '''
        pass

    def get_server_info(self, server_id: str) -> Dict[str, Any]:
        '''Get server details by ID.
        Args:
            server_id: Server ID
        Returns:
            Dict[str, Any]: Server metadata dict
        Raises:
            requests.RequestException
            ValueError
        '''
        pass

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        '''Find server by name.
        Args:
            name: Server name
        Returns:
            Optional[Dict[str, Any]]: Server metadata dict or None
        Raises:
            requests.RequestException
        '''
        pass

    def find_server_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        '''Find server by ID (UUID) or exact name.
        Efficient: Direct API call for UUID or name match.
        Args:
            reference: Server ID or exact name
        Returns:
            Optional[Dict[str, Any]]: Server metadata dict or None
        Raises:
            requests.RequestException
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings preserve all original requirements, types, and behaviors without adding, dropping, or altering any specifications._

---

## 11. RealClassEval/post_cut-off/snippet_281 — `llm_lexical_01` (lexical)

**Original**

```python

class FewShotFormat:
    '''Handler for different few-shot example formats'''
    @staticmethod
    def convert(examples: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        '''Convert any supported format to input-output format'''
        pass
    @staticmethod
    def validate(examples: List[Dict[str, Any]]) -> bool:
        '''Validate that examples are in input-output format'''
        pass
```

**Rewrite**

```python

class FewShotFormat:
    '''Manages a variety of few-shot example formats'''
    @staticmethod
    def convert(examples: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        '''Transforms any compatible format into input-output format'''
        pass
    @staticmethod
    def validate(examples: List[Dict[str, Any]]) -> bool:
        '''Verifies that examples conform to input-output format'''
        pass
```

_judge: EQUIVALENT — The docstrings use synonymous verbs ("Convert"/"Transforms", "Validate"/"Verifies") and equivalent phrasing ("supported format"/"compatible format", "are in"/"conform to") without changing any functional requirement, type, or behavior._

---

## 12. RealClassEval/csn/snippet_250 — `llm_terse_01` (terse)

**Original**

```python
class MHMSBFormat:
    '''MHMSBFormat'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Set a given pixel to a color.'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Get the color of a given pixel'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''completely fill/clear the buffer with a color'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''Draw a rectangle at the given location, size and color. The ``fill_rect`` method draws
        both the outline and interior.'''
        pass
```

**Rewrite**

```python
class MHMSBFormat:
    '''MHMSBFormat'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Set pixel (x,y) to color'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Get color of pixel (x,y)'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''Fill buffer with color'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''fill_rect: draws rectangle at (x,y) with width,height and color, filling outline and interior'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use more concise phrasing but describe identical requirements for all methods without altering parameters, behavior, or outcomes._

---

## 13. RealClassEval/csn/snippet_163 — `llm_lexical_01` (lexical)

**Original**

```python

class WebVTTStyleBlock:
    '''Representation of a style block.'''

    def __init__(self, text: str):
        '''
        Initialize.
        :param text: style text
        '''
        pass
    @classmethod
    def is_valid(cls, lines: typing.Sequence[str]) -> bool:
        '''
        Validate the lines for a match of a style block.
        :param lines: the lines to be validated
        :returns: true for a matching style block
        '''
        pass
    @classmethod
    def from_lines(cls, lines: typing.Iterable[str]) -> 'WebVTTStyleBlock':
        '''
        Create a `WebVTTStyleBlock` from lines of text.
        :param lines: the lines of text
        :returns: `WebVTTStyleBlock` instance
        '''
        pass
    @staticmethod
    def format_lines(lines: typing.List[str]) -> typing.List[str]:
        '''
        Return the lines for a style block.
        :param lines: style lines
        :returns: list of lines for a style block
        '''
        pass
```

**Rewrite**

```python

class WebVTTStyleBlock:
    '''A class for representing a style block.'''

    def __init__(self, text: str):
        '''
        Initialize the instance using the provided style text.
        '''
        pass
    @classmethod
    def is_valid(cls, lines: typing.Sequence[str]) -> bool:
        '''
        Determine whether the given lines constitute a valid style block pattern.
        :param lines: the lines to be examined
        :returns: True if the lines match a style block structure
        '''
        pass
    @classmethod
    def from_lines(cls, lines: typing.Iterable[str]) -> 'WebVTTStyleBlock':
        '''
        Construct a WebVTTStyleBlock instance from text lines.
        :param lines: the text lines
        :returns: an instance of the WebVTTStyleBlock class
        '''
        pass
    @staticmethod
    def format_lines(lines: typing.List[str]) -> typing.List[str]:
        '''
        Produce the formatted output lines for a style block.
        :param lines: the raw style lines
        :returns: a list of strings representing the style block lines
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase requirements with synonymous language (e.g., "Validate" → "Determine whether", "Create" → "Construct") without changing parameter types, return value semantics, or behavioral expectations._

---

## 14. RealClassEval/post_cut-off/snippet_243 — `llm_lexical_01` (lexical)

**Original**

```python
class PrintAndFlushSink:
    '''A Loguru sink.
    forcibly prints each log record and flushes immediately,
    mimicking print(..., flush=True).
    '''

    def write(self, message: str):
        '''Write a message to the stream and flush immediately.
        Args:
            message (str): The message to write.
        '''
        pass

    def flush(self):
        '''Flush the stream.
        Already flushed on every write call.
        '''
        pass
```

**Rewrite**

```python
class PrintAndFlushSink:
    '''A sink module for Loguru that mandatorily outputs every log entry and triggers an immediate flush operation, emulating the flush=True parameter behavior of Python's print() function.
    '''

    def write(self, message: str):
        '''Output the specified string value to the underlying stream and enforce an immediate flush. Args:
            message (str): The text content to be written to the stream.
        '''
        pass

    def flush(self):
        '''Force a flush of the stream contents. Note that this action occurs automatically during each write() invocation.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing without changing any functional requirement, argument type, or behavioral specification._

---

## 15. RealClassEval/csn/snippet_81 — `llm_lexical_01` (lexical)

**Original**

```python

class ChDir:
    '''
    Context manager that changes the current working directory and then
    returns you to where you were.
    This is nearly the same as the stdlib :func:`contextlib.chdir`, with the
    exception that it will do nothing if the input path is None (i.e. the user
    did not want to change directories).
    SeeAlso:
        :func:`contextlib.chdir`
    Example:
        >>> import ubelt as ub
        >>> dpath = ub.Path.appdir('ubelt/tests/chdir').ensuredir()
        >>> dir1 = (dpath / 'dir1').ensuredir()
        >>> dir2 = (dpath / 'dir2').ensuredir()
        >>> with ChDir(dpath):
        >>>     assert ub.Path.cwd() == dpath
        >>>     # change to the given directory, and then returns back
        >>>     with ChDir(dir1):
        >>>         assert ub.Path.cwd() == dir1
        >>>         with ChDir(dir2):
        >>>             assert ub.Path.cwd() == dir2
        >>>             # changes inside the context manager will be reset
        >>>             os.chdir(dpath)
        >>>         assert ub.Path.cwd() == dir1
        >>>     assert ub.Path.cwd() == dpath
        >>>     with ChDir(dir1):
        >>>         assert ub.Path.cwd() == dir1
        >>>         with ChDir(None):
        >>>             assert ub.Path.cwd() == dir1
        >>>             # When disabled, the cwd does *not* reset at context exit
        >>>             os.chdir(dir2)
        >>>         assert ub.Path.cwd() == dir2
        >>>         os.chdir(dir1)
        >>>         # Dont change dirs, but reset to your cwd at context end
        >>>         with ChDir('.'):
        >>>             os.chdir(dir2)
        >>>         assert ub.Path.cwd() == dir1
        >>>     assert ub.Path.cwd() == dpath
    '''

    def __init__(self, dpath):
        '''
        Args:
            dpath (str | PathLike | None):
                The new directory to work in.
                If None, then the context manager is disabled.
        '''
        pass

    def __enter__(self):
        '''
        Returns:
            ChDir: self
        '''
        pass

    def __exit__(self, ex_type, ex_value, ex_traceback):
        '''
        Args:
            ex_type (Type[BaseException] | None):
            ex_value (BaseException | None):
            ex_traceback (TracebackType | None):
        Returns:
            bool | None
        '''
        pass
```

**Rewrite**

```python

class ChDir:
    '''
    Utility for managing directory changes within a confined code block, automatically reverting to the original working directory upon exiting the scope.
    This class largely mirrors the behavior of the standard library's :func:`contextlib.chdir` function, except it completely bypasses the directory change when the provided path is None (indicating the user intends to skip the alteration).
    SeeAlso:
        :func:`contextlib.chdir`
    Example:
        >>> import ubelt as ub
        >>> dpath = ub.Path.appdir('ubelt/tests/chdir').ensuredir()
        >>> dir1 = (dpath / 'dir1').ensuredir()
        >>> dir2 = (dpath / 'dir2').ensuredir()
        >>> with ChDir(dpath):
        >>>     assert ub.Path.cwd() == dpath
        >>>     # change to the given directory, and then returns back
        >>>     with ChDir(dir1):
        >>>         assert ub.Path.cwd() == dir1
        >>>         with ChDir(dir2):
        >>>             assert ub.Path.cwd() == dir2
        >>>             # changes inside the context manager will be reset
        >>>             os.chdir(dpath)
        >>>         assert ub.Path.cwd() == dir1
        >>>     assert ub.Path.cwd() == dpath
        >>>     with ChDir(dir1):
        >>>         assert ub.Path.cwd() == dir1
        >>>         with ChDir(None):
        >>>             assert ub.Path.cwd() == dir1
        >>>             # When disabled, the cwd does *not* reset at context exit
        >>>             os.chdir(dir2)
        >>>         assert ub.Path.cwd() == dir2
        >>>         os.chdir(dir1)
        >>>         # Dont change dirs, but reset to your cwd at context end
        >>>         with ChDir('.'):
        >>>             os.chdir(dir2)
        >>>         assert ub.Path.cwd() == dir1
        >>>     assert ub.Path.cwd() == dpath
    '''

    def __init__(self, dpath):
        '''
        Arguments:
            dpath (str | PathLike | None):
                Target directory for the directory switch operation.
                Specifying None deactivates the context manager's directory alteration feature.
        '''
        pass

    def __enter__(self):
        '''
        Returns:
            The ChDir instance (self)
        '''
        pass

    def __exit__(self, ex_type, ex_value, ex_traceback):
        '''
        Arguments:
            ex_type (Type[BaseException] | None):
                Class of the exception that was raised, or None if no exception occurred.
            ex_value (BaseException | None):
                Instance of the raised exception, or None if no exception was thrown.
            ex_traceback (TracebackType | None):
                Traceback object associated with the exception, or None if no exception happened.
        Returns:
            Either a boolean or None value.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite preserves all functional requirements and technical specifications without altering behavior, types, or conditions for any input._

---

## 16. RealClassEval/csn/snippet_157 — `llm_terse_01` (terse)

**Original**

```python
class HashMixin:
    '''Keyed hash mixin.
    `HashMixin` uses 'pgcrypto' to encrypt data in a postgres database.
    '''

    def __init__(self, original=None, *args, **kwargs):
        '''Tells the init the original attr.'''
        pass

    def pre_save(self, model_instance, add):
        '''Save the original_value.'''
        pass

    def get_placeholder(self, value=None, compiler=None, connection=None):
        '''
        Tell postgres to encrypt this field with a hashing function.
        The `value` string is checked to determine if we need to hash or keep
        the current value.
        `compiler` and `connection` is ignored here as we don't need custom operators.
        '''
        pass

    def get_encrypt_sql(self, connection):
        '''Get encrypt sql. This may be overidden by some implementations.'''
        pass
```

**Rewrite**

```python
class HashMixin:
    '''Keyed hash mixin for pgcrypto postgres data encryption
    '''

    def __init__(self, original=None, *args, **kwargs):
        '''Sets original attr'''
        pass

    def pre_save(self, model_instance, add):
        '''Save original_value'''
        pass

    def get_placeholder(self, value=None, compiler=None, connection=None):
        '''
        Encrypt field with pgcrypto
        `value` check: hash or keep
        `compiler` and `connection` ignored (no custom operators)
        '''
        pass

    def get_encrypt_sql(self, connection):
        '''Get encrypt sql (may be overridden)'''
        pass
```

_judge: EQUIVALENT — The rewritten specification rephrases the same requirements without changing any technical meaning, behavior, or constraints._

---

## 17. RealClassEval/csn/snippet_111 — `llm_formal_01` (formal)

**Original**

```python
class Connection:
    '''Connection class'''
    @staticmethod
    def getInstance():
        '''Static access method.'''
        pass

    def __init__(self):
        '''Virtually private constructor.'''
        pass
```

**Rewrite**

```python
class Connection:
    '''A connection is represented by this class.'''
    @staticmethod
    def getInstance():
        '''Access to a connection instance is provided by this static method.'''
        pass

    def __init__(self):
        '''Virtual private access is marked for this constructor.'''
        pass
```

_judge: EQUIVALENT — The docstring revisions only enhance clarity and detail without changing the core Singleton requirements, return types, or behavioral constraints._

---

## 18. RealClassEval/csn/snippet_218 — `llm_lexical_01` (lexical)

**Original**

```python
class RepeatValueIndicator:
    '''Represent a repeating value.'''

    def __init__(self, key: str) -> None:
        '''Init with key.'''
        pass

    def __repr__(self) -> str:
        '''Return representation.'''
        pass
```

**Rewrite**

```python
class RepeatValueIndicator:
    '''Denotes a value that repeats.'''

    def __init__(self, key: str) -> None:
        '''Initialize the object with the key argument.'''
        pass

    def __repr__(self) -> str:
        '''Provide the string representation of the instance.'''
        pass
```

_judge: EQUIVALENT — The docstrings use synonymous phrasing without changing the described behavior, requirements, or input handling._

---

## 19. RealClassEval/csn/snippet_75 — `llm_terse_01` (terse)

**Original**

```python
class Geometry:
    '''
    Abstract parent class for geotypes
    '''

    def geojson(self):
        '''
        Returns a GeoJSON string representation of this geotype, compliant to
        RFC 7946 (https://tools.ietf.org/html/rfc7946)
        :return: str
        '''
        pass

    def to_dict(self):
        '''
        Returns a dict representation of this geotype
        :return: dict
        '''
        pass
```

**Rewrite**

```python
class Geometry:
    '''
    Abstract base class for geotypes
    '''

    def geojson(self):
        '''
        GeoJSON string per RFC 7946
        '''
        pass

    def to_dict(self):
        '''
        dict representation
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses more concise language without changing the core requirements of the class or its methods._

---

## 20. RealClassEval/csn/snippet_213 — `llm_lexical_01` (lexical)

**Original**

```python
class BaseAuthenticationMiddleware:
    '''Base class for all authentication middleware classes.
    Args:
        user_storage (BaseUserStorage): a storage object used to retrieve
            user object using their identifier lookup.
        name (str): custom name of the authentication middleware useful
            for handling custom user storage backends. Defaults to middleware
            class name.
    .. versionadded:: 0.4.0
    '''

    def __init__(self, user_storage=None, name=None):
        '''Initialize authentication middleware.'''
        pass

    def process_resource(self, req, resp, resource, uri_kwargs=None):
        '''Process resource after routing to it.
        This is basic falcon middleware handler.
        Args:
            req (falcon.Request): request object
            resp (falcon.Response): response object
            resource (object): resource object matched by falcon router
            uri_kwargs (dict): additional keyword argument from uri template.
                For ``falcon<1.0.0`` this is always ``None``
        '''
        pass

    def identify(self, req, resp, resource, uri_kwargs):
        '''Identify the user that made the request.
        Args:
            req (falcon.Request): request object
            resp (falcon.Response): response object
            resource (object): resource object matched by falcon router
            uri_kwargs (dict): additional keyword argument from uri template.
                For ``falcon<1.0.0`` this is always ``None``
        Returns:
            object: a user object (preferably a dictionary).
        '''
        pass

    def try_storage(self, identifier, req, resp, resource, uri_kwargs):
        '''Try to find user in configured user storage object.
        Args:
            identifier: User identifier.
        Returns:
            user object.
        '''
        pass
```

**Rewrite**

```python
class BaseAuthenticationMiddleware:
    '''Serves as the foundational class for implementing various authentication middleware components.
    Args:
        user_storage (BaseUserStorage): an object responsible for fetching user data via identifier queries
        name (str): an optional label for the middleware instance, particularly beneficial when interfacing with non-default user storage systems. If not specified, defaults to the class name of the middleware.
    .. versionadded:: 0.4.0
    '''

    def __init__(self, user_storage=None, name=None):
        '''Sets up the base authentication middleware instance.'''
        pass

    def process_resource(self, req, resp, resource, uri_kwargs=None):
        '''Handles the resource following route matching. This constitutes fundamental Falcon framework middleware processing.
        Args:
            req (falcon.Request): the incoming request
            resp (falcon.Response): the outgoing response
            resource (object): the resource instance selected by the router
            uri_kwargs (dict): extra parameters extracted from the URI template; for Falcon versions prior to 1.0.0, this value is invariably None
        '''
        pass

    def identify(self, req, resp, resource, uri_kwargs):
        '''Determines the user associated with the incoming request.
        Args:
            req (falcon.Request): the request object
            resp (falcon.Response): the response object
            resource (object): the resource object routed by Falcon
            uri_kwargs (dict): additional URI template-derived keyword arguments; for Falcon <1.0.0, this is consistently None
        Returns:
            object: a user instance (ideally represented as a dictionary).
        '''
        pass

    def try_storage(self, identifier, req, resp, resource, uri_kwargs):
        '''Attempts to locate the user within the configured storage backend.
        Args:
            identifier: The user's identifier value.
        Returns:
            the user object
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification rephrases all docstrings using synonymous language without changing any requirements, argument meanings, return types, or examples._

---

## 21. RealClassEval/csn/snippet_207 — `llm_formal_01` (formal)

**Original**

```python
class IJavaStreamParser:
    '''
    API of the Java stream parser
    '''

    def run(self):
        '''
        Parses the input stream
        '''
        pass

    def dump(self, content):
        '''
        Dumps to a string the given objects
        '''
        pass

    def _read_content(self, type_code, block_data, class_desc=None):
        '''
        Parses the next content. Use with care (use only in a transformer)
        '''
        pass
```

**Rewrite**

```python
class IJavaStreamParser:
    '''
    Provides an application programming interface for parsing Java streams.
    '''

    def run(self):
        '''
        The input stream is parsed by the run method.
        '''
        pass

    def dump(self, content):
        '''
        The given objects are dumped to a string by the dump method.
        '''
        pass

    def _read_content(self, type_code, block_data, class_desc=None):
        '''
        The next content is parsed by the _read_content method. This method must only be used in a transformer context.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using passive voice and slightly different wording but convey identical constraints and behaviors without changing any technical specifications._

---

## 22. RealClassEval/post_cut-off/snippet_293 — `llm_lexical_01` (lexical)

**Original**

```python

class KNNModel:
    '''
    Thin wrapper around sklearn NearestNeighbors for cosine similarity retrieval.
    :ivar model: Fitted NearestNeighbors instance.
    :vartype model: NearestNeighbors
    :ivar k: Default number of neighbors.
    :vartype k: int
    '''

    def __init__(self, items, k=3):
        '''
        Initialize KNN index.
        :param items: Iterable of (item_id, embedding_vector) pairs.
        :type items: Iterable[Tuple[Any, Sequence[float]]]
        :param k: Default number of neighbors to retrieve.
        :type k: int
        '''
        pass

    def neighbors(self, target_emb, k=None):
        '''
        Retrieve k nearest neighbors by cosine distance.
        :param target_emb: Query embedding vector.
        :type target_emb: Sequence[float]
        :param k: Override number of neighbors (defaults to self.k).
        :type k: int
        :return: List of (item_id, distance) pairs ordered by proximity.
        :rtype: List[Tuple[Any, float]]
        '''
        pass
```

**Rewrite**

```python

class KNNModel:
    '''
    Lightweight adapter for sklearn's NearestNeighbors enabling cosine similarity searches.
    :ivar model: The trained NearestNeighbors model instance.
    :vartype model: NearestNeighbors
    :ivar k: The default count of nearest neighbors to return.
    :vartype k: int
    '''

    def __init__(self, items, k=3):
        '''
        Sets up the K-nearest neighbors index.
        :param items: Collection containing item identifiers paired with their embedding vectors.
        :type items: Iterable[Tuple[Any, Sequence[float]]]
        :param k: The default quantity of neighbors to fetch.
        :type k: int
        '''
        pass

    def neighbors(self, target_emb, k=None):
        '''
        Identifies the k nearest neighbors to the query vector based on cosine distance.
        :param target_emb: The vector representing the query for which neighbors are sought.
        :type target_emb: Sequence[float]
        :param k: Number of neighbors to return; if unspecified, uses the instance's default value (self.k).
        :type k: int
        :return: A list of tuples containing item identifiers and their cosine distances, sorted from nearest to farthest.
        :rtype: List[Tuple[Any, float]]
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing and clarifies implicit details (e.g., "cosine distances", "sorted from nearest to farthest") without altering any requirements, types, or behavioral contracts._

---

## 23. RealClassEval/csn/snippet_153 — `llm_terse_01` (terse)

**Original**

```python

class SelectorPattern:
    '''Selector pattern.'''

    def __init__(self, name: str, pattern: str) -> None:
        '''Initialize.'''
        pass

    def get_name(self) -> str:
        '''Get name.'''
        pass

    def match(self, selector: str, index: int, flags: int) -> Match[str] | None:
        '''Match the selector.'''
        pass
```

**Rewrite**

```python

class SelectorPattern:
    '''Selector pattern'''

    def __init__(self, name: str, pattern: str) -> None:
        '''Init'''
        pass

    def get_name(self) -> str:
        '''Name'''
        pass

    def match(self, selector: str, index: int, flags: int) -> Match[str] | None:
        '''Match selector'''
        pass
```

_judge: EQUIVALENT — The docstring wording changes (e.g., "Initialize" vs "Init", omission of "the") are stylistic and do not alter the semantic requirements of the class or its methods._

---

## 24. RealClassEval/csn/snippet_260 — `llm_lexical_01` (lexical)

**Original**

```python
class Pattern:
    '''A single pattern for either inclusion or exclusion.'''

    def __init__(self, spec, inclusive):
        '''Create regex-based pattern matcher from glob `spec`.'''
        pass

    def __str__(self):
        '''Return inclusiveness indicator and original glob pattern.'''
        pass

    def matches(self, path):
        '''Check this pattern against given `path`.'''
        pass
```

**Rewrite**

```python
class Pattern:
    '''A solitary pattern specifying inclusion or exclusion behavior.'''

    def __init__(self, spec, inclusive):
        '''Instantiate a regex pattern matcher derived from the provided glob `spec`.'''
        pass

    def __str__(self):
        '''Emit a string containing the inclusion flag and source glob pattern.'''
        pass

    def matches(self, path):
        '''Check whether the given `path` matches this pattern.'''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing without altering requirements, types, or behavior described in the original docstrings._

---

## 25. RealClassEval/post_cut-off/snippet_47 — `llm_terse_01` (terse)

**Original**

```python

class Convolve2DFullFill:
    '''
    Initial implementation of convolve2d_full_fill task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the Convolve2DFullFill.'''
        pass

    def solve(self, problem):
        '''
        Compute the 2D convolution of arrays a and b using "full" mode and "fill" boundary.
        Uses scipy.signal.fftconvolve for efficiency, which implicitly handles "fill" boundary.
        Args:
            problem: A tuple (a, b) of 2D arrays.
        Returns:
            A 2D array containing the convolution result.
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Check if the provided solution is valid.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

**Rewrite**

```python

class Convolve2DFullFill:
    '''
    convolve2d_full_fill task initial implementation, OpenEvolve evolution for perf/correctness
    '''

    def __init__(self):
        '''Convolve2DFullFill init'''
        pass

    def solve(self, problem):
        '''
        2D conv of a,b in full/fill mode via scipy.signal.fftconvolve
        Args:
            problem: A tuple (a, b) of 2D arrays.
        Returns:
            A 2D array containing the convolution result.
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Solution validity check
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

_judge: EQUIVALENT — The rewrite condenses docstring wording without changing specified behavior, requirements, or implementation details._

---

## 26. RealClassEval/post_cut-off/snippet_289 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class UpdateRuleDeployment:
    '''Model for updating rule deployment.'''

    def __post_init__(self):
        '''Post initilizaiton for validating/converting attributes'''
        pass

    def to_dict(self) -> Dict[str, Any]:
        '''Convert to dictionary for JSON serialization.'''
        pass
```

**Rewrite**

```python
@dataclass
class UpdateRuleDeployment:
    '''Update rule deployment'''

    def __post_init__(self):
        '''Post-init attribute validation and conversion'''
        pass

    def to_dict(self) -> Dict[str, Any]:
        '''Convert to JSON-serializable dict'''
        pass
```

_judge: EQUIVALENT — The docstrings convey identical requirements with only stylistic rewording (e.g., "Model for" vs. direct phrase, "dictionary for JSON serialization" vs. "JSON-serializable dict")._

---

## 27. RealClassEval/post_cut-off/snippet_239 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class Tag:
    '''
    Represents a tag in the N8n system.
    Attributes:
        name: Tag name (required)
        id
        createdAt
        updatedAt
    '''

    def to_dict(self):
        '''Convert the tag to a dictionary for API requests'''
        pass
    @classmethod
    def from_dict(cls, data):
        '''Create a Tag instance from API response data'''
        pass
```

**Rewrite**

```python
@dataclass
class Tag:
    '''
    N8n tag: name (required), id, createdAt, updatedAt
    '''

    def to_dict(self):
        '''Convert tag to API request dict'''
        pass
    @classmethod
    def from_dict(cls, data):
        '''Create Tag from API response data'''
        pass
```

_judge: EQUIVALENT — The rewrite condenses the attribute description without changing the required status of 'name' or the list of attributes._

---

## 28. RealClassEval/csn/snippet_129 — `llm_terse_01` (terse)

**Original**

```python
class FenwickNode:
    '''Fenwick Tree node.'''

    def __init__(self, parent, children, index=None):
        '''Fenwick Tree node. Single parent and multiple children.
        :param FenwickNode parent: a parent node
        :param list(FenwickNode) children: a list of children nodes
        :param int index: node label
        '''
        pass

    def get_ancestors(self):
        '''Returns a list of ancestors of the node. Ordered from the earliest.
        :return: node's ancestors, ordered from most recent
        :rtype: list(FenwickNode)
        '''
        pass
```

**Rewrite**

```python
class FenwickNode:
    '''Fenwick tree node'''

    def __init__(self, parent, children, index=None):
        '''Fenwick tree node: single parent, multiple children
        :param FenwickNode parent: parent node
        :param list(FenwickNode) children: children nodes
        :param int index: node label
        '''
        pass

    def get_ancestors(self):
        '''earliest, most recent ancestors list
        :return: earliest, most recent ancestors list
        :rtype: list(FenwickNode)
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and minor stylistic changes without altering any functional requirements, parameter types, return values, or behavioral constraints._

---

## 29. RealClassEval/post_cut-off/snippet_297 — `llm_formal_01` (formal)

**Original**

```python

class MASVisualizer:
    '''Utility for visualizing Multi-Agent System interactions'''

    def __init__(self, output_dir=None):
        '''
        Initialize the MAS visualizer.
        Args:
            output_dir: Directory to save visualization HTML files
        '''
        pass

    def generate_html(self, visualization_data, title=None):
        '''
        Generate HTML for visualizing agent interactions using D3.js.
        Args:
            visualization_data: Dictionary with nodes and links data
            title: Optional title for the visualization
        Returns:
            HTML string
        '''
        pass

    def visualize(self, visualization_file, output_file=None, open_browser=True):
        '''
        Generate an HTML visualization from a visualization data file and open in browser.
        Args:
            visualization_file: Path to the visualization data JSON file
            output_file: Optional path to save the HTML output
            open_browser: Whether to open the visualization in a browser (default: True)
        Returns:
            Path to the generated HTML file
        '''
        pass

    def visualize_from_agent_system(self, agent_system, problem_id=None):
        '''
        Generate visualizations for all visualization files from an agent system.
        Args:
            agent_system: AgentSystem instance
            problem_id: Optional problem ID to filter by
        Returns:
            List of paths to generated HTML files
        '''
        pass
```

**Rewrite**

```python

class MASVisualizer:
    '''Provides visualization capabilities for interactions within Multi-Agent Systems.'''

    def __init__(self, output_dir=None):
        '''
        The MAS visualizer is initialized.
        The parameter output_dir specifies a directory path for saving visualization HTML files.
        '''
        pass

    def generate_html(self, visualization_data, title=None):
        '''
        The method generates an HTML string for visualizing agent interactions using the D3.js library.
        The parameter visualization_data is a dictionary containing nodes and links data for the visualization.
        The parameter title is optional and specifies the title of the visualization.
        The method returns an HTML string.
        '''
        pass

    def visualize(self, visualization_file, output_file=None, open_browser=True):
        '''
        The method generates an HTML visualization by reading a visualization data file.
        The visualization_file parameter is a path to a JSON file containing visualization data.
        The output_file parameter is an optional path to save the generated HTML output as a file.
        The open_browser parameter is a boolean with a default value of True, indicating whether to open the visualization in a web browser.
        The method returns the file path of the generated HTML file.
        '''
        pass

    def visualize_from_agent_system(self, agent_system, problem_id=None):
        '''
        The method generates HTML visualizations for all visualization files associated with the given agent system.
        The agent_system parameter is an instance of the AgentSystem class.
        The problem_id parameter is an optional identifier used to filter visualization files by a specific problem.
        The method returns a list of file paths for the generated HTML files.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification rephrases parameter and return value descriptions without changing requirements, types, meanings, or behaviors._

---

## 30. RealClassEval/post_cut-off/snippet_291 — `llm_terse_01` (terse)

**Original**

```python
class ProgressScope:
    '''Scope for tracking progress of an operation.'''

    def __init__(self, context: 'MCPContext', total: int, description: str):
        '''
        Initialize a progress scope.
        Args:
            context: The parent MCPContext
            total: Total number of steps
            description: Description of the operation
        '''
        pass

    def update(self, step: int=1) -> None:
        '''
        Update progress by a number of steps.
        Args:
            step: Number of steps to add to progress
        '''
        pass

    def set_progress(self, current: int) -> None:
        '''
        Set progress to a specific value.
        Args:
            current: Current progress value
        '''
        pass
```

**Rewrite**

```python
class ProgressScope:
    '''Operation progress scope'''

    def __init__(self, context: 'MCPContext', total: int, description: str):
        '''
        Initialize progress scope
        Args:
            context: parent MCPContext
            total: total steps
            description: operation description
        '''
        pass

    def update(self, step: int=1) -> None:
        '''
        Update progress by steps
        Args:
            step: steps to add
        '''
        pass

    def set_progress(self, current: int) -> None:
        '''
        Set current progress
        Args:
            current: current progress
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing without altering any functional requirements, argument semantics, or behavioral expectations._

---

## 31. RealClassEval/post_cut-off/snippet_21 — `llm_formal_01` (formal)

**Original**

```python
@dataclass
class MCPTool:
    '''Represents an MCP tool.'''
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPTool':
        '''Create a Tool from a dictionary.'''
        pass

    def to_dict(self) -> Dict[str, Any]:
        '''Convert the tool to a dictionary.'''
        pass

    def to_tool_schema(self) -> Dict[str, Any]:
        '''Convert the tool to a tool schema.'''
        pass
```

**Rewrite**

```python
@dataclass
class MCPTool:
    '''A representation for an MCP tool is provided by this class.'''
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPTool':
        '''A Tool instance is created from a dictionary.'''
        pass

    def to_dict(self) -> Dict[str, Any]:
        '''The tool is converted to a dictionary.'''
        pass

    def to_tool_schema(self) -> Dict[str, Any]:
        '''The tool is converted to a tool schema.'''
        pass
```

_judge: EQUIVALENT — The docstrings are rephrased in passive voice but convey identical requirements without altering behavior, types, or examples._

---

## 32. RealClassEval/post_cut-off/snippet_72 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class SessionAgent:
    '''Agent that belongs to a Session.'''
    @classmethod
    def from_agent(cls, agent: 'Agent') -> 'SessionAgent':
        '''Convert an Agent to a SessionAgent.'''
        pass
    @classmethod
    def from_dict(cls, env: dict[str, Any]) -> 'SessionAgent':
        '''Initialize a SessionAgent from a dictionary, ignoring keys that are not class parameters.'''
        pass

    def to_dict(self) -> dict[str, Any]:
        '''Convert the SessionAgent to a dictionary representation.'''
        pass
```

**Rewrite**

```python
@dataclass
class SessionAgent:
    '''Session-associated agent'''
    @classmethod
    def from_agent(cls, agent: 'Agent') -> 'SessionAgent':
        '''SessionAgent from Agent'''
        pass
    @classmethod
    def from_dict(cls, env: dict[str, Any]) -> 'SessionAgent':
        '''Dict factory, ignore extra keys'''
        pass

    def to_dict(self) -> dict[str, Any]:
        '''SessionAgent dict representation'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use more concise phrasing but preserve identical technical requirements for initialization, dictionary conversion, and key handling._

---

## 33. RealClassEval/csn/snippet_156 — `llm_formal_01` (formal)

**Original**

```python
class SimpleService:
    '''Hold information about an access service enabled on a dataset.
    Attributes
    ----------
    name : str
        The name of the service
    service_type : str
        The service type (i.e. "OPENDAP", "NetcdfSubset", "WMS", etc.)
    access_urls : dict[str, str]
        A dictionary of access urls whose keywords are the access service
        types defined in the catalog (for example, "OPENDAP", "NetcdfSubset",
        "WMS", etc.)
    '''

    def __init__(self, service_node):
        '''Initialize the Dataset object.
        Parameters
        ----------
        service_node : :class:`~xml.etree.ElementTree.Element`
            An :class:`~xml.etree.ElementTree.Element` representing a service node
        '''
        pass

    def is_resolver(self):
        '''Return whether the service is a resolver service.'''
        pass
```

**Rewrite**

```python
class SimpleService:
    '''Contains information about an access service enabled on a dataset.

    Attributes:
    name
        Type: string
        Description: The name of the service instance.
    service_type
        Type: string
        Description: The service type identifier, such as "OPENDAP", "NetcdfSubset", or "WMS".
    access_urls
        Type: dict[str, str]
        Description: A dictionary mapping access service type keywords (as defined in the catalog) to their corresponding URLs. Examples of keywords include "OPENDAP", "NetcdfSubset", and "WMS".
    '''

    def __init__(self, service_node):
        '''Initializes the Dataset object.

        Parameters:
        service_node
            An instance of :class:`~xml.etree.ElementTree.Element` representing a service node in the XML configuration.
        '''
        pass

    def is_resolver(self):
        '''Returns true if the service is a resolver service, false otherwise.'''
        pass
```

_judge: EQUIVALENT — All differences are in wording and tone without altering the meaning of requirements, types, or behaviors._

---

## 34. RealClassEval/post_cut-off/snippet_45 — `llm_formal_01` (formal)

**Original**

```python

class TokenBucketRateLimiter:
    '''
    Token Bucket Rate Limiter Implementation
    The token bucket algorithm allows for a burst of traffic up to the bucket capacity,
    while maintaining a steady rate of token refill.
    '''

    def __init__(self, tokens_per_second: int, bucket_capacity: Optional[int]=None):
        '''
        Initialize token bucket rate limiter.
        Args:
            tokens_per_second: Rate at which tokens are refilled
            bucket_capacity: Maximum number of tokens in bucket (defaults to tokens_per_second)
        '''
        pass

    def _refill_tokens(self):
        '''Refill tokens based on time elapsed since last refill.'''
        pass

    def try_consume_token(self) -> bool:
        '''
        Try to consume a token from the bucket.
        Returns:
            True if token was consumed, False if bucket is empty
        '''
        pass

    def get_wait_time(self) -> float:
        '''
        Calculate how long to wait before a token will be available.
        Returns:
            Time in seconds to wait
        '''
        pass
```

**Rewrite**

```python

class TokenBucketRateLimiter:
    '''
    The token bucket algorithm is implemented to permit bursts of traffic up to the bucket capacity and to refill tokens at a steady rate.
    '''

    def __init__(self, tokens_per_second: int, bucket_capacity: Optional[int]=None):
        '''
        The token bucket is initialized with a refill rate of tokens_per_second tokens per second and a bucket capacity of bucket_capacity tokens; bucket_capacity defaults to tokens_per_second.
        '''
        pass

    def _refill_tokens(self):
        '''Tokens are refilled based on the time elapsed since the last refill operation.'''
        pass

    def try_consume_token(self) -> bool:
        '''
        A return value of true indicates successful token consumption; a return value of false indicates an empty bucket.
        '''
        pass

    def get_wait_time(self) -> float:
        '''
        The time in seconds until a token becomes available is returned.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases the docstrings using synonymous language without changing any requirements, types, or behavioral semantics described in the original specification._

---

## 35. RealClassEval/csn/snippet_42 — `llm_formal_01` (formal)

**Original**

```python

class WifiManager:
    '''
    Simulates Android WifiManager.
    @see: http://developer.android.com/reference/android/net/wifi/WifiManager.html
    '''

    def __init__(self, device):
        '''
        Constructor.
        :param device:
        :type device:
        '''
        pass

    def getWifiState(self):
        '''
        Gets the Wi-Fi enabled state.
        @return: One of WIFI_STATE_DISABLED, WIFI_STATE_DISABLING, WIFI_STATE_ENABLED, WIFI_STATE_ENABLING, WIFI_STATE_UNKNOWN
        '''
        pass
```

**Rewrite**

```python

class WifiManager:
    '''
    The Android WifiManager class is simulated by this class. @see: http://developer.android.com/reference/android/net/wifi/WifiManager.html
    '''

    def __init__(self, device):
        '''
        The constructor has a parameter named device.
        '''
        pass

    def getWifiState(self):
        '''
        The Wi-Fi enabled state is returned as one of WIFI_STATE_DISABLED, WIFI_STATE_DISABLING, WIFI_STATE_ENABLED, WIFI_STATE_ENABLING, or WIFI_STATE_UNKNOWN
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases the docstrings using different wording and structure but conveys identical requirements for parameters, return values, and examples without adding, dropping, or altering any technical specifications._

---

## 36. RealClassEval/csn/snippet_288 — `llm_terse_01` (terse)

**Original**

```python

class Aspect:
    '''A network, ansible_host, system, deploy, configure or contextualize element in a RADL.'''

    def getId(self):
        '''Return the id of the aspect.'''
        pass

    def clone(self):
        '''Return a copy of this aspect.'''
        pass
```

**Rewrite**

```python

class Aspect:
    '''RADL network, ansible_host, system, deploy, configure, contextualize element'''

    def getId(self):
        '''aspect id'''
        pass

    def clone(self):
        '''aspect copy'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings omit functional verbs and articles but preserve identical requirements for class elements and method behaviors._

---

## 37. RealClassEval/csn/snippet_250 — `llm_lexical_01` (lexical)

**Original**

```python
class MHMSBFormat:
    '''MHMSBFormat'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Set a given pixel to a color.'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Get the color of a given pixel'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''completely fill/clear the buffer with a color'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''Draw a rectangle at the given location, size and color. The ``fill_rect`` method draws
        both the outline and interior.'''
        pass
```

**Rewrite**

```python
class MHMSBFormat:
    '''Provides functionality for managing framebuffer data in the MHMSB format.'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Assigns the specified color value to the pixel at the provided coordinates.'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Retrieves the color value stored at the given pixel location.'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''Fills the entire buffer area with the designated color, removing all prior content.'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''Renders a rectangle starting from the supplied coordinates with the defined width, height, and fill color. 
        The operation draws both the rectangular boundary and the enclosed area.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing without changing the required behavior, input handling, or output semantics of any method._

---

## 38. RealClassEval/csn/snippet_36 — `llm_formal_01` (formal)

**Original**

```python
@dataclass
class Sentence:
    '''
A data class representing the distance measure for one sentence.
    '''

    def empty(self) -> bool:
        '''
Test whether this sentence includes any ranked phrases.
    returns:
`True` if the `phrases` is not empty.
        '''
        pass

    def text(self, doc: Doc) -> str:
        '''
Accessor for the text slice of the `spaCy` [`Doc`](https://spacy.io/api/doc)
document represented by this sentence.
    doc:
source document
    returns:
the sentence text
        '''
        pass
```

**Rewrite**

```python
@dataclass
class Sentence:
    '''
A data class that represents the distance measure for a single sentence.
    '''

    def empty(self) -> bool:
        '''
The method returns `True` if the `phrases` attribute of the instance is non-empty.
        '''
        pass

    def text(self, doc: Doc) -> str:
        '''
The method returns the text span of the sentence represented by the instance within the `spaCy` `Doc` document provided as the `doc` parameter.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and clarifies attribute references without changing the specified behavior, requirements, or input/output semantics._

---

## 39. RealClassEval/csn/snippet_218 — `llm_formal_01` (formal)

**Original**

```python
class RepeatValueIndicator:
    '''Represent a repeating value.'''

    def __init__(self, key: str) -> None:
        '''Init with key.'''
        pass

    def __repr__(self) -> str:
        '''Return representation.'''
        pass
```

**Rewrite**

```python
class RepeatValueIndicator:
    '''A repeating value indicator is provided by this class.'''

    def __init__(self, key: str) -> None:
        '''The instance is initialized using the key.'''
        pass

    def __repr__(self) -> str:
        '''A representation of the instance is returned.'''
        pass
```

_judge: EQUIVALENT — The docstrings use paraphrased language but describe identical requirements without altering types, arguments, behavior, or examples._

---

## 40. RealClassEval/csn/snippet_131 — `llm_lexical_01` (lexical)

**Original**

```python

class NullFunc:
    '''
    A trivial class that acts as a placeholder "do nothing" function.
        '''

    def __call__(self, *args):
        '''
        Returns meaningless output no matter what the input(s) is.  If no input,
        returns None.  Otherwise, returns an array of NaNs (or a single NaN) of
        the same size as the first input.
        '''
        pass

    def distance(self, other):
        '''
        Trivial distance metric that only cares whether the other object is also
        an instance of NullFunc.  Intentionally does not inherit from HARKobject
        as this might create dependency problems.
        Parameters
        ----------
        other : any
            Any object for comparison to this instance of NullFunc.
        Returns
        -------
        (unnamed) : float
            The distance between self and other.  Returns 0 if other is also a
            NullFunc; otherwise returns an arbitrary high number.
        '''
        pass
```

**Rewrite**

```python

class NullFunc:
    '''
    A minimal class functioning as a dummy function substitute.
        '''

    def __call__(self, *args):
        '''
        Produces arbitrary worthless results regardless of provided arguments. In absence of inputs, returns None; with inputs, it generates NaN values matching the dimensionality of the first parameter.
        '''
        pass

    def distance(self, other):
        '''
        Simple distance computation exclusively checking if the other object belongs to the NullFunc class. Purposefully avoids inheritance from HARKobject to circumvent dependency issues.
        Parameters
        ----------
        other : any
            Any object provided for comparison with this NullFunc instance.
        Returns
        -------
        (unnamed) : float
            Computed distance value; returns zero if other is also a NullFunc instance, otherwise an arbitrary large constant.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing ("trivial" vs "minimal", "meaningless" vs "worthless", "high number" vs "large constant") but preserves all behavioral requirements, types, and examples exactly._

---

## 41. RealClassEval/post_cut-off/snippet_56 — `llm_lexical_01` (lexical)

**Original**

```python

class FFTComplexScipyFFTpack:
    '''
    Initial implementation of fft_cmplx_scipy_fftpack task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the FFTComplexScipyFFTpack.'''
        pass

    def solve(self, problem):
        '''
        Solve the fft_cmplx_scipy_fftpack problem.
        Args:
            problem: Dictionary containing problem data specific to fft_cmplx_scipy_fftpack
        Returns:
            The solution in the format expected by the task
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Check if the provided solution is valid.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

**Rewrite**

```python

class FFTComplexScipyFFTpack:
    '''
    First version of the fft_cmplx_scipy_fftpack task.
    This implementation will undergo iterative refinement via OpenEvolve to enhance efficiency and accuracy.
    '''

    def __init__(self):
        '''Construct a new FFTComplexScipyFFTpack object.'''
        pass

    def solve(self, problem):
        '''
        Address the fft_cmplx_scipy_fftpack problem.
        Args:
            problem: Dictionary holding the specific inputs for fft_cmplx_scipy_fftpack
        Returns:
            Computed result matching the task's required output structure
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Assess whether the candidate solution satisfies the original problem.
        Args:
            problem: The initial problem specification
            solution: Proposed answer to validate
        Returns:
            True for a valid solution, False for an invalid one
        '''
        pass
```

_judge: EQUIVALENT — The docstrings rephrase requirements with synonymous terms (e.g., "solve" vs "address", "valid" vs "satisfies the problem") without changing specifications, types, or behavior._

---

## 42. RealClassEval/post_cut-off/snippet_351 — `llm_terse_01` (terse)

**Original**

```python

class AgentInfo:
    '''Agent information container supporting both Python and YAML agents.'''

    def __init__(self, name: str, description: str, file_path: Path | None=None, module: 'ModuleType | None'=None, yaml_document: 'YamlAgentDocument | None'=None) -> None:
        '''Initialize agent info.
        Args:
            name: Agent name
            description: Agent description
            file_path: Path to agent file/directory
            module: Python module (for Python agents)
            yaml_document: YAML agent document (for YAML agents)
        '''
        pass
    @property
    def kind(self) -> Literal['python', 'yaml']:
        '''Get the definition type of the agent.'''
        pass
    @property
    def path(self) -> str:
        '''Get the definition path of the agent.'''
        pass
```

**Rewrite**

```python

class AgentInfo:
    '''Python/YAML agent info container'''

    def __init__(self, name: str, description: str, file_path: Path | None=None, module: 'ModuleType | None'=None, yaml_document: 'YamlAgentDocument | None'=None) -> None:
        '''Initialize agent info
        Args:
            name: agent name
            description: agent description
            file_path: agent file/directory path
            module: Python agent module
            yaml_document: YAML agent doc
        '''
        pass
    @property
    def kind(self) -> Literal['python', 'yaml']:
        '''Agent definition type'''
        pass
    @property
    def path(self) -> str:
        '''Agent definition path'''
        pass
```

_judge: EQUIVALENT — The rewrite uses more concise phrasing without changing any requirement, type, or meaning of the class, arguments, or properties._

---

## 43. RealClassEval/csn/snippet_120 — `llm_terse_01` (terse)

**Original**

```python
class NestedDummyClass:
    '''Nested dummy class for testing method resolution.'''

    def run(self):
        '''Do nothing.'''
        pass
    @property
    def prop(self):
        '''Property.'''
        pass
```

**Rewrite**

```python
class NestedDummyClass:
    '''Nested dummy method resolution test class'''

    def run(self):
        '''No-op'''
        pass
    @property
    def prop(self):
        '''Property'''
        pass
```

_judge: EQUIVALENT — The docstring rephrasings ("Do nothing" → "No-op", "class for testing method resolution" → "method resolution test class") are synonymous and preserve identical behavioral requirements._

---

## 44. RealClassEval/csn/snippet_203 — `llm_lexical_01` (lexical)

**Original**

```python

class MegKDE:
    '''Matched Elliptical Gaussian Kernel Density Estimator
    Adapted from the algorithm specified in the BAMBIS's model specified Wolf 2017
    to support weighted samples.
    '''

    def __init__(self, train: np.ndarray, weights: np.ndarray | None=None, truncation: float=3.0, nmin: int=4, factor: float=1.0):
        '''
        Args:
            train (np.ndarray): The training data set. Should be a 1D array of samples or a 2D array
                of shape (n_samples, n_dim).
            weights (np.ndarray, optional): An array of weights. If not specified, equal weights are assumed.
            truncation (float, optional): The maximum deviation (in sigma) to use points in the KDE
            nmin (int, optional): The minimum number of points required to estimate the density
            factor (float, optional): Send bandwidth to this factor of the data estimate
        '''
        pass

    def evaluate(self, data: np.ndarray) -> np.ndarray:
        '''Estimate un-normalised probability density at target points
        Args:
            data (np.ndarray): 2D array of shape (n_samples, n_dim).
        Returns:
            np.ndarray: A `(n_samples)` length array of estimates
        '''
        pass
```

**Rewrite**

```python

class MegKDE:
    '''Aligned Elliptical Gaussian Kernel Density Estimator
    Based on Wolf's 2017 BAMBIS model algorithm
    Now extended to accommodate weighted samples
    '''

    def __init__(self, train: np.ndarray, weights: np.ndarray | None=None, truncation: float=3.0, nmin: int=4, factor: float=1.0):
        '''
        Args:
            train (np.ndarray): Dataset used for training. Must be either a 1D array of samples or a 2D array with shape (n_samples, n_dim).
            weights (np.ndarray, optional): Array of sample weights. Uniform weights apply by default if unspecified.
            truncation (float, optional): Maximum sigma deviation permitted for point inclusion in the KDE calculation
            nmin (int, optional): Minimum point count required to perform density estimation
            factor (float, optional): Multiplier applied to the automatically derived bandwidth estimate
        '''
        pass

    def evaluate(self, data: np.ndarray) -> np.ndarray:
        '''Compute unnormalized probability density values at specified target locations
        Parameters:
            data (np.ndarray): Target points array with dimensions (n_samples, n_dim)
        Returns:
            np.ndarray: Array containing density estimates of length (n_samples) for each input sample
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases documentation using synonymous terms and slightly different wording without changing technical requirements, types, or behavioral specifications._

---

## 45. RealClassEval/csn/snippet_230 — `llm_terse_01` (terse)

**Original**

```python
class RawPacket:
    '''RawPacket
    Wraps a packet such that:
        packet.raw.fieldname
    returns the value of fieldname as a raw value with no enumeration
    substitutions or DN to EU conversions applied.
    '''

    def __init__(self, packet):
        '''Creates a new RawPacket based on the given Packet.'''
        pass

    def __getattr__(self, fieldname):
        '''Returns the value of the given packet fieldname as a raw
        value with no DN to EU conversion applied.
        '''
        pass
```

**Rewrite**

```python
class RawPacket:
    '''RawPacket
    raw packet field access without enum or DN-EU conversion
    '''

    def __init__(self, packet):
        '''Constructs RawPacket from packet'''
        pass

    def __getattr__(self, fieldname):
        '''Returns raw value for fieldname without DN-EU conversion
        '''
        pass
```

_judge: EQUIVALENT — The rewrite condenses the original requirements into equivalent concise phrasing without altering any technical specifications or behaviors._

---

## 46. RealClassEval/csn/snippet_159 — `llm_lexical_01` (lexical)

**Original**

```python

class Style:
    '''Representation of a style.'''

    def __init__(self, text: typing.Union[str, typing.List[str]]):
        '''Initialize.
        :param: text: the style text
        '''
        pass
    @property
    def text(self):
        '''Return the text of the style.'''
        pass
```

**Rewrite**

```python

class Style:
    '''Class modeling a style.'''

    def __init__(self, text: typing.Union[str, typing.List[str]]):
        ''':param: text: the style's textual representation
        '''
        pass
    @property
    def text(self):
        '''Returns the style's text.'''
        pass
```

_judge: EQUIVALENT — The docstring changes only in phrasing (e.g., "text" vs "textual representation", "Return" vs "Returns") without altering any requirement, type, or behavior specification._

---

## 47. RealClassEval/csn/snippet_144 — `llm_terse_01` (terse)

**Original**

```python

class InGivenDirectory:
    '''Change directory to given directory for duration of ``with`` block.
    Useful when you want to use `InTemporaryDirectory` for the final test, but
    you are still debugging.  For example, you may want to do this in the end:
    >>> with InTemporaryDirectory() as tmpdir:
    ...     # do something complicated which might break
    ...     pass
    But indeed the complicated thing does break, and meanwhile the
    ``InTemporaryDirectory`` context manager wiped out the directory with the
    temporary files that you wanted for debugging.  So, while debugging, you
    replace with something like:
    >>> with InGivenDirectory() as tmpdir: # Use working directory by default
    ...     # do something complicated which might break
    ...     pass
    You can then look at the temporary file outputs to debug what is happening,
    fix, and finally replace ``InGivenDirectory`` with ``InTemporaryDirectory``
    again.
    '''

    def __init__(self, path=None):
        '''Initialize directory context manager.
        Parameters
        ----------
        path : None or str, optional
            path to change directory to, for duration of ``with`` block.
            Defaults to ``os.getcwd()`` if None
        '''
        pass

    def __enter__(self):
        '''Chdir to the managed directory, creating it if needed.'''
        pass

    def __exit__(self, exc, value, tb):
        '''Revert the working directory.'''
        pass
```

**Rewrite**

```python

class InGivenDirectory:
    '''Change directory during with block.
    >>> with InTemporaryDirectory() as tmpdir:
    ...     # do something complicated which might break
    ...     pass
    >>> with InGivenDirectory() as tmpdir: # Use working directory by default
    ...     # do something complicated which might break
    ...     pass
    '''

    def __init__(self, path=None):
        '''Initialize directory context manager.
        path=None|str optional - directory for with block (default os.getcwd)
        '''
        pass

    def __enter__(self):
        '''Change to managed directory, create if needed.'''
        pass

    def __exit__(self, exc, value, tb):
        '''Revert working directory.'''
        pass
```

_judge: EQUIVALENT — The rewrite keeps the same functional requirements (default path, chdir, create if needed, revert) and examples, only removing explanatory prose._

---

## 48. RealClassEval/post_cut-off/snippet_226 — `llm_lexical_01` (lexical)

**Original**

```python

class PriceFormatter:
    '''Utility class for formatting prices and quantities consistently.'''
    @staticmethod
    def format_price_for_display(price: Union[float, int, None]) -> str:
        '''
        Format price for user display (UI, console output).
        Args:
            price: Price value to format
        Returns:
            Formatted price string with currency symbol
        '''
        pass
    @staticmethod
    def format_price_for_logging(price: Union[float, int, None]) -> str:
        '''
        Format price for logging (more precision, with currency symbol).
        Args:
            price: Price value to format
        Returns:
            Formatted price string for logging
        '''
        pass
    @staticmethod
    def format_quantity(quantity: Union[float, int, None]) -> str:
        '''
        Format quantity for display.
        Args:
            quantity: Quantity value to format
        Returns:
            Formatted quantity string
        '''
        pass
    @staticmethod
    def format_percentage(percentage: Union[float, int, None]) -> str:
        '''
        Format percentage for display.
        Args:
            percentage: Percentage value to format (as decimal, e.g., 0.05 for 5%)
        Returns:
            Formatted percentage string
        '''
        pass
    @staticmethod
    def format_price_for_display(price: Union[float, int, None]) -> str:
        '''
        Format price without currency symbol, preserving precision.
        Args:
            price: Price value to format
            force_precision: Optional forced decimal places
        Returns:
            Formatted price string without currency symbol
        '''
        pass
    @staticmethod
    def format_currency(price: Union[float, int, None], currency: str='USD') -> str:
        '''
        Format price with currency symbol.
        Args:
            price: Price value to format
            currency: Currency code (USD, EUR, BTC, etc.)
        Returns:
            Formatted price string with currency symbol
        '''
        pass
```

**Rewrite**

```python

class PriceFormatter:
    '''Class designed to uniformly format monetary amounts and item counts'''
    @staticmethod
    def format_price_for_display(price: Union[float, int, None]) -> str:
        '''
        Prepare a price value for end-user presentation in graphical interfaces or command-line outputs
        Args:
            price: Price value to format
        Returns:
            Formatted price string with currency symbol
        '''
        pass
    @staticmethod
    def format_price_for_logging(price: Union[float, int, None]) -> str:
        '''
        Generate a log-entry representation of a price featuring enhanced numerical detail and currency symbol
        Args:
            price: Price value to format
        Returns:
            Formatted price string for logging
        '''
        pass
    @staticmethod
    def format_quantity(quantity: Union[float, int, None]) -> str:
        '''
        Create a display-friendly string representation of a quantity value
        Args:
            quantity: Quantity value to format
        Returns:
            Formatted quantity string
        '''
        pass
    @staticmethod
    def format_percentage(percentage: Union[float, int, None]) -> str:
        '''
        Convert a decimal percentage value (e.g., 0.05 for 5%) into a human-readable formatted string
        Args:
            percentage: Percentage value to format (as decimal, e.g., 0.05 for 5%)
        Returns:
            Formatted percentage string
        '''
        pass
    @staticmethod
    def format_price_for_display(price: Union[float, int, None]) -> str:
        '''
        Produce a numeric price string excluding currency symbols while maintaining original decimal precision
        Args:
            price: Price value to format
            force_precision: Optional forced decimal places
        Returns:
            Formatted price string without currency symbol
        '''
        pass
    @staticmethod
    def format_currency(price: Union[float, int, None], currency: str='USD') -> str:
        '''
        Assemble a currency-symbol-augmented string representation for a price value
        Args:
            price: Price value to format
            currency: Currency code (USD, EUR, BTC, etc.)
        Returns:
            Formatted price string with currency symbol
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification describes identical functional requirements for each method with equivalent precision in meaning, only rephrasing wording without altering behavior, arguments, return values, or examples._

---

## 49. RealClassEval/post_cut-off/snippet_141 — `llm_lexical_01` (lexical)

**Original**

```python
class GoalRedirectionTemplate:
    '''
    GoalRedirectionTemplate class for enhancing attacks with goal redirection patterns.
    Designed to work with any agentic vulnerability type by making attacks appear as legitimate
    goal modifications, constraint adjustments, or operational refinements.
    Universal Enhancement Approach:
    - Compatible with all vulnerability types (permission escalation, data access, decision manipulation, etc.)
    - Adapts goal framing to different operational contexts
    - Provides flexible redirection patterns that enhance any underlying attack vector
    - Works across security, behavioral, and functional vulnerability domains
    '''
    @staticmethod
    def enhance_ambiguous_framing(attack: str) -> str:
        '''
        Enhance attack with ambiguous framing techniques.
        Universal pattern for contextual goal interpretation across all vulnerability types.
        '''
        pass
    @staticmethod
    def enhance_priority_shifting(attack: str) -> str:
        '''
        Enhance attack with priority shifting techniques.
        Dynamic priority adjustment that works with any vulnerability context.
        '''
        pass
    @staticmethod
    def enhance_constraint_confusion(attack: str) -> str:
        '''
        Enhance attack with constraint confusion patterns.
        Multi-constraint optimization for complex vulnerability scenarios.
        '''
        pass
    @staticmethod
    def enhance_goal_drift(attack: str) -> str:
        '''
        Enhance attack with goal drift techniques.
        Natural evolution pattern that adapts to any vulnerability type.
        '''
        pass
    @staticmethod
    def enhance_scope_expansion(attack: str) -> str:
        '''
        Enhance attack with scope expansion techniques.
        Comprehensive scope enhancement for maximum vulnerability coverage.
        '''
        pass
    @staticmethod
    def enhance_operational_alignment(attack: str) -> str:
        '''
        Enhance attack with operational alignment techniques.
        New method for aligning goals with any vulnerability operational context.
        '''
        pass
```

**Rewrite**

```python
class GoalRedirectionTemplate:
    '''
    Class GoalRedirectionTemplate enables attack enhancement via goal redirection strategies. Designed to operate with any agent-driven vulnerability by disguising malicious actions as legitimate objective changes, constraint modifications, or operational improvements. Universal Enhancement Framework:
    - Functions across all vulnerability categories (permission escalation, data access, decision manipulation, etc.)
    - Modifies objective framing within varying operational settings
    - Supplies adaptable redirection tactics that strengthen any foundational attack method
    - Applies effectively throughout security, behavioral, and functional vulnerability landscapes
    '''
    @staticmethod
    def enhance_ambiguous_framing(attack: str) -> str:
        '''
        Augment attack using ambiguous framing methodologies. A universal pattern for interpreting goals within any vulnerability context across all vulnerability categories.
        '''
        pass
    @staticmethod
    def enhance_priority_shifting(attack: str) -> str:
        '''
        Strengthen attack employing priority shifting methods. Adaptive priority modification applicable to any vulnerability scenario.
        '''
        pass
    @staticmethod
    def enhance_constraint_confusion(attack: str) -> str:
        '''
        Improve attack through constraint confusion patterns. Multi-dimensional constraint optimization tailored for intricate vulnerability situations.
        '''
        pass
    @staticmethod
    def enhance_goal_drift(attack: str) -> str:
        '''
        Bolster attack via goal drift techniques. Organic evolution approach that conforms to any vulnerability classification.
        '''
        pass
    @staticmethod
    def enhance_scope_expansion(attack: str) -> str:
        '''
        Amplify attack using scope expansion strategies. Broadened scope augmentation engineered for maximum vulnerability coverage.
        '''
        pass
    @staticmethod
    def enhance_operational_alignment(attack: str) -> str:
        '''
        Refine attack with operational alignment techniques. Novel synchronization method for harmonizing objectives with the operational environment of any vulnerability.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous language (e.g., "enhance" vs "augment", "techniques" vs "methodologies") but preserves identical requirements, argument types, return types, and behavioral intent across all methods and the class description._

---

## 50. RealClassEval/csn/snippet_53 — `llm_terse_01` (terse)

**Original**

```python
class Bits:
    '''Breaks an integer into a specified number of True/False bits.'''

    def __init__(self, num_bits):
        '''Initialize the number of bits.'''
        pass

    def __call__(self, val):
        '''Convert the integer to the list of True/False values.'''
        pass
```

**Rewrite**

```python
class Bits:
    '''Fixed-length boolean list from integer'''

    def __init__(self, num_bits):
        '''Set num_bits'''
        pass

    def __call__(self, val):
        '''Integer to boolean list'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings describe identical requirements for the class, initializer, and callable method without altering technical specifications or behavior._

---

## 51. RealClassEval/post_cut-off/snippet_339 — `llm_lexical_01` (lexical)

**Original**

```python

class MCPConfigGenerator:
    '''Generator for MCP server configuration.'''

    def __init__(self, base_dir: Optional[str]=None):
        '''
        Initialize the MCP config generator.
        Args:
            base_dir: Base directory for resolving relative paths (defaults to current working directory)
        '''
        pass

    def generate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        '''
        Generate a full MCP server configuration from a simplified config.
        Args:
            config: Simplified configuration dictionary
        Returns:
            Complete MCP server configuration
        '''
        pass

    def write_config(self, config: Dict[str, Any], output_path: str) -> None:
        '''
        Write the generated configuration to a file.
        Args:
            config: The simplified configuration dictionary
            output_path: Path to write the generated configuration
        '''
        pass
```

**Rewrite**

```python

class MCPConfigGenerator:
    '''Generates MCP server configurations.'''

    def __init__(self, base_dir: Optional[str]=None):
        '''
        Sets up the MCP configuration generator.
        Args:
            base_dir: Directory path used for resolving relative paths (defaults to current working directory)
        '''
        pass

    def generate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        '''
        Creates a complete MCP server configuration from a simplified input dictionary.
        Args:
            config: The simplified configuration provided as a dictionary
        Returns:
            The full MCP server configuration
        '''
        pass

    def write_config(self, config: Dict[str, Any], output_path: str) -> None:
        '''
        Writes the generated MCP server configuration to a file.
        Args:
            config: The simplified configuration dictionary
            output_path: Path to the output file for the generated configuration
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification rephrases docstring wording without changing any requirements, types, arguments, return values, or behavior._

---

## 52. RealClassEval/post_cut-off/snippet_189 — `llm_terse_01` (terse)

**Original**

```python

class RateLimiter:
    '''Convenience class for enforcing rates in loops.'''

    def __init__(self, hz):
        '''
        Args:
            hz (int): frequency to enforce
        '''
        pass

    def sleep(self, env):
        '''Attempt to sleep at the specified rate in hz.'''
        pass
```

**Rewrite**

```python

class RateLimiter:
    '''Loop rate limiter'''

    def __init__(self, hz):
        '''
        hz (int): loop frequency
        '''
        pass

    def sleep(self, env):
        '''Try sleep at hz'''
        pass
```

_judge: EQUIVALENT — The docstring wording changes (e.g., "Convenience class for enforcing rates" to "Loop rate limiter") do not alter the core requirements, types, or behaviors described._

---

## 53. RealClassEval/csn/snippet_104 — `llm_formal_01` (formal)

**Original**

```python
class BufferSegment:
    '''Represents a segment within a ``BufferWithSegments``.
    This type is essentially a reference to N bytes within a
    ``BufferWithSegments``.
    The object conforms to the buffer protocol.
    '''
    @property
    def offset(self):
        '''The byte offset of this segment within its parent buffer.'''
        pass

    def __len__(self):
        '''Obtain the length of the segment, in bytes.'''
        pass

    def tobytes(self):
        '''Obtain bytes copy of this segment.'''
        pass
```

**Rewrite**

```python
class BufferSegment:
    '''Represents a reference to N bytes within an instance of ``BufferWithSegments``.
    The object conforms to the buffer protocol.
    '''
    @property
    def offset(self):
        '''The value of this attribute is the byte offset of the segment within its parent buffer.'''
        pass

    def __len__(self):
        '''The length of the segment in bytes is returned.'''
        pass

    def tobytes(self):
        '''A bytes copy of the segment is returned.'''
        pass
```

_judge: EQUIVALENT — The docstrings use different wording but describe identical requirements for the class, its offset property, length method, and tobytes method._

---

## 54. RealClassEval/post_cut-off/snippet_339 — `llm_terse_01` (terse)

**Original**

```python

class MCPConfigGenerator:
    '''Generator for MCP server configuration.'''

    def __init__(self, base_dir: Optional[str]=None):
        '''
        Initialize the MCP config generator.
        Args:
            base_dir: Base directory for resolving relative paths (defaults to current working directory)
        '''
        pass

    def generate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        '''
        Generate a full MCP server configuration from a simplified config.
        Args:
            config: Simplified configuration dictionary
        Returns:
            Complete MCP server configuration
        '''
        pass

    def write_config(self, config: Dict[str, Any], output_path: str) -> None:
        '''
        Write the generated configuration to a file.
        Args:
            config: The simplified configuration dictionary
            output_path: Path to write the generated configuration
        '''
        pass
```

**Rewrite**

```python

class MCPConfigGenerator:
    '''MCP server config generator'''

    def __init__(self, base_dir: Optional[str]=None):
        '''
        Initialize MCP config generator
        Args:
            base_dir: Base dir for resolving relative paths (default: cwd)
        '''
        pass

    def generate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        '''
        Generate MCP server config from simplified config
        Args:
            config: Simplified config dict
        Returns:
            Complete MCP server config
        '''
        pass

    def write_config(self, config: Dict[str, Any], output_path: str) -> None:
        '''
        Write generated config to file
        Args:
            config: Simplified config dict
            output_path: Path to write config
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses abbreviations and rephrasing (e.g., "config" instead of "configuration", "dir" instead of "directory", "cwd" instead of "current working directory") but preserves all functional requirements, argument types, and behavioral semantics without altering any meaning or co_

---

## 55. RealClassEval/csn/snippet_153 — `llm_formal_01` (formal)

**Original**

```python

class SelectorPattern:
    '''Selector pattern.'''

    def __init__(self, name: str, pattern: str) -> None:
        '''Initialize.'''
        pass

    def get_name(self) -> str:
        '''Get name.'''
        pass

    def match(self, selector: str, index: int, flags: int) -> Match[str] | None:
        '''Match the selector.'''
        pass
```

**Rewrite**

```python

class SelectorPattern:
    '''A selector pattern is defined.'''

    def __init__(self, name: str, pattern: str) -> None:
        '''The selector pattern is initialized.'''
        pass

    def get_name(self) -> str:
        '''The name of the selector pattern is obtained.'''
        pass

    def match(self, selector: str, index: int, flags: int) -> Match[str] | None:
        '''The selector is matched.'''
        pass
```

_judge: EQUIVALENT — The docstring wording changes are rephrasings that do not alter the meaning of any requirement._

---

## 56. RealClassEval/csn/snippet_229 — `llm_formal_01` (formal)

**Original**

```python
class PacketContext:
    '''PacketContext
    A PacketContext provides a simple wrapper around a Packet so that
    field accesses of the form:
        packet.fieldname
    may also be specified as:
        packet[fieldname]
    This latter syntax allows a PacketContext to be used as a symbol
    table when evaluating PacketExpressions.
    '''

    def __init__(self, packet):
        '''Creates a new PacketContext for the given Packet.'''
        pass

    def __getitem__(self, name):
        '''Returns packet[name]'''
        pass
```

**Rewrite**

```python
class PacketContext:
    '''The PacketContext class wraps a Packet object, permitting field access via indexed notation (packet[fieldname]) in addition to standard dot notation (packet.fieldname). The indexed access enables the PacketContext to function as a symbol table during evaluation of PacketExpressions.
    '''

    def __init__(self, packet):
        '''A new PacketContext instance is created for the specified Packet.'''
        pass

    def __getitem__(self, name):
        '''packet[name] is returned.'''
        pass
```

_judge: EQUIVALENT — The rewritten specification conveys identical requirements about the class behavior without altering any details of the PacketContext's functionality or interface._

---

## 57. RealClassEval/post_cut-off/snippet_239 — `llm_formal_01` (formal)

**Original**

```python
@dataclass
class Tag:
    '''
    Represents a tag in the N8n system.
    Attributes:
        name: Tag name (required)
        id
        createdAt
        updatedAt
    '''

    def to_dict(self):
        '''Convert the tag to a dictionary for API requests'''
        pass
    @classmethod
    def from_dict(cls, data):
        '''Create a Tag instance from API response data'''
        pass
```

**Rewrite**

```python
@dataclass
class Tag:
    '''
    This class represents a tag in the N8n system. The attributes are 'name' (required), 'id', 'createdAt', and 'updatedAt'.
    '''

    def to_dict(self):
        '''The tag is converted to a dictionary for API requests by this method.'''
        pass
    @classmethod
    def from_dict(cls, data):
        '''A Tag instance is constructed from API response data by this method.'''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases the docstrings using passive voice and minor syntactic changes but preserves the exact same requirements for attributes, method purposes, and behavior._

---

## 58. RealClassEval/csn/snippet_204 — `llm_terse_01` (terse)

**Original**

```python
class AuthenticationBase:
    '''Base class for API authentication components.
    Authentication components are responsible for extracting the request
    credentials, if any. They should raise a 401 if the credentials are
    invalid, but should provide `None` for unauthenticated users.
    Flask-RESTy provides an implementation using `JSON Web Tokens`_  but you
    can use any authentication component by extending
    :py:class:`AuthenticationBase` and implementing
    :py:meth:`get_request_credentials`.
    .. _JSON Web Tokens: https://jwt.io/
    '''

    def authenticate_request(self):
        '''Store the request credentials in the
        :py:class:`flask.ctx.AppContext`.
        .. warning::
            No validation is performed by Flask-RESTy. It is up to the
            implementor to validate the request in
            :py:meth:`get_request_credentials`.
        '''
        pass

    def get_request_credentials(self):
        '''Get the credentials for the current request.
        Typically this is done by inspecting :py:data:`flask.request`.
        .. warning::
            Implementing classes **must** raise an exception on authentication
            failure. A 401 Unauthorized :py:class:`ApiError` is recommended.
        :return: The credentials for the current request.
        '''
        pass
```

**Rewrite**

```python
class AuthenticationBase:
    '''Base class for API auth components.
    Extract request credentials (if any); raise 401 on invalid, return None for unauthenticated
    Flask-RESTy implements JWT; extend and implement :py:meth:`get_request_credentials` for other auth
    .. _JSON Web Tokens: https://jwt.io/
    '''

    def authenticate_request(self):
        '''Store credentials in :py:class:`flask.ctx.AppContext`.
        .. warning:: No validation by Flask-RESTy; implementor must validate in :py:meth:`get_request_credentials`.
        '''
        pass

    def get_request_credentials(self):
        '''Get current request credentials
        Typically via :py:data:`flask.request`
        .. warning:: Implementing classes must raise on auth failure; 401 Unauthorized :py:class:`ApiError` recommended
        :return: Current request credentials
        '''
        pass
```

_judge: EQUIVALENT — The core requirements for credential extraction, 401 handling on invalid credentials, None return for unauthenticated users, and Flask-RESTy's validation warning are preserved without altering any technical specifications or behaviors._

---

## 59. RealClassEval/post_cut-off/snippet_373 — `llm_formal_01` (formal)

**Original**

```python

class _TPCDataGenerator:
    '''
    Base class for TPC data generation. PLEASE DO NOT INSTANTIATE THIS CLASS DIRECTLY. Use the TPCHDataGenerator and TPCDSDataGenerator
    subclasses instead.
        '''

    def __init__(self, scale_factor: int, target_mount_folder_path: str=None, target_row_group_size_mb: int=128):
        '''
        Initialize the TPC data generator with a scale factor.
        :param scale_factor: The scale factor for the data generation.
        '''
        pass

    def run(self):
        '''
        This method uses DuckDB to generate in-memory tables based on the specified 
        scale factor and writes them to Parquet files. It estimates the average row 
        size in MB using a sample of the data since DuckDB only supports specifying 
        the number of rows per row group. The generated tables are written to the 
        specified target folder with optimized row group sizes.
        Parameters
        ----------
        None
        Notes
        -----
        - The method creates a sample Parquet file for each table to estimate row sizes.
        - The full table is then written as Parquet files with optimized row group sizes.
        - Temporary files and in-memory tables are cleaned up after processing.
        '''
        pass
```

**Rewrite**

```python

class _TPCDataGenerator:
    '''
    This class serves as a base for TPC data generation. Direct instantiation of the class is prohibited; the TPCHDataGenerator and TPCDSDataGenerator subclasses shall be used for data generation.
        '''

    def __init__(self, scale_factor: int, target_mount_folder_path: str=None, target_row_group_size_mb: int=128):
        '''
        The TPC data generator is initialized with a scale_factor parameter representing the scale factor for data generation.
        '''
        pass

    def run(self):
        '''
        The run method generates TPC data tables in memory using DuckDB and writes the resulting Parquet files to the specified target folder.
        Average row size in megabytes is estimated by creating a sample Parquet file for each table, as DuckDB only supports specifying row group size in terms of the number of rows rather than the size.
        The full tables are then written as Parquet files with row group sizes optimized based on the estimated average row sizes.
        Temporary files and in-memory tables are cleaned up upon completion of the method.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification maintains identical technical requirements for the class behavior, parameters, and method operations without altering any constraints or semantics._

---

## 60. RealClassEval/csn/snippet_229 — `llm_lexical_01` (lexical)

**Original**

```python
class PacketContext:
    '''PacketContext
    A PacketContext provides a simple wrapper around a Packet so that
    field accesses of the form:
        packet.fieldname
    may also be specified as:
        packet[fieldname]
    This latter syntax allows a PacketContext to be used as a symbol
    table when evaluating PacketExpressions.
    '''

    def __init__(self, packet):
        '''Creates a new PacketContext for the given Packet.'''
        pass

    def __getitem__(self, name):
        '''Returns packet[name]'''
        pass
```

**Rewrite**

```python
class PacketContext:
    '''PacketContext
    This class encapsulates a Packet instance within a minimal container,
    enabling field retrieval via dot notation (e.g., packet.fieldname)
    to be equivalently executed using bracket syntax (e.g., packet['fieldname']).
    This dictionary-based approach allows the PacketContext to function
    as a symbol table during packet expression evaluations.
    '''

    def __init__(self, packet):
        '''Instantiates a PacketContext object tied to the designated Packet.'''
        pass

    def __getitem__(self, name):
        '''Provides the value located in the packet for the specified key 'name'.'''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases the docstrings and method descriptions without changing the core requirements, types, or behavior of the class._

---

## 61. RealClassEval/post_cut-off/snippet_113 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class BiomniConfig:
    '''Central configuration for Biomni agent.
    All settings are optional and have sensible defaults.
    API keys are still read from environment variables to maintain
    compatibility with existing .env file structure.
    Usage:
        # Create config with defaults
        config = BiomniConfig()
        # Override specific settings
        config = BiomniConfig(llm="gpt-4", timeout_seconds=1200)
        # Modify after creation
        config.path = "./custom_data"
    '''

    def __post_init__(self):
        '''Load any environment variable overrides if they exist.'''
        pass

    def to_dict(self) -> dict:
        '''Convert config to dictionary for easy access.'''
        pass
```

**Rewrite**

```python
@dataclass
class BiomniConfig:
    '''Biomni agent configuration
    Settings optional with defaults
    API keys read from .env for compatibility
        # Create config with defaults
        config = BiomniConfig()
        # Override specific settings
        config = BiomniConfig(llm="gpt-4", timeout_seconds=1200)
        # Modify after creation
        config.path = "./custom_data"
    '''

    def __post_init__(self):
        '''Load env overrides if exist'''
        pass

    def to_dict(self) -> dict:
        '''Config to dict for access'''
        pass
```

_judge: EQUIVALENT — The docstrings describe identical requirements with only phrasing differences that don't alter meaning, examples, or behavior._

---

## 62. RealClassEval/csn/snippet_8 — `llm_formal_01` (formal)

**Original**

```python
class RecordProcess:
    '''A class representing a process record with ID and name.
    Attributes
    ----------
    id : int
        The process ID
    name : str
        The process name
    '''

    def __init__(self, id_, name):
        '''Initialize a RecordProcess instance.
        Parameters
        ----------
        id_ : int
            The process ID
        name : str
            The process name
        '''
        pass

    def __repr__(self):
        '''Return string representation of RecordProcess.
        Returns
        -------
        str
            Formatted string with id and name
        '''
        pass

    def __format__(self, spec):
        '''Format the RecordProcess instance.
        Parameters
        ----------
        spec : str
            Format specification
        Returns
        -------
        str
            Formatted ID according to specification
        '''
        pass
```

**Rewrite**

```python
class RecordProcess:
    '''A class that represents a process record containing an identifier and a name.
    Attributes
    ----------
    id : int
        An integer attribute representing the process identifier.
    name : str
        A string attribute representing the process name.
    '''

    def __init__(self, id_, name):
        '''An instance of RecordProcess is initialized by this method.
        Parameters
        ----------
        id_ : int
            An integer value that is the process identifier.
        name : str
            A string value that is the process name.
        '''
        pass

    def __repr__(self):
        '''A string representation of the RecordProcess instance is returned.
        Returns
        -------
        str
            A string containing the process identifier and process name.
        '''
        pass

    def __format__(self, spec):
        '''The RecordProcess instance is formatted according to the provided specification.
        Parameters
        ----------
        spec : str
            A format specification string.
        Returns
        -------
        str
            A string representing the process identifier formatted according to the specification.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous terms and descriptive phrasing without changing types, meanings, or behavioral requirements of any component._

---

## 63. RealClassEval/post_cut-off/snippet_103 — `llm_formal_01` (formal)

**Original**

```python

class TritonRemoteModel:
    '''
    Client for interacting with a remote Triton Inference Server model.
    Attributes:
        endpoint (str): The name of the model on the Triton server.
        url (str): The URL of the Triton server.
        triton_client: The Triton client (either HTTP or gRPC).
        InferInput: The input class for the Triton client.
        InferRequestedOutput: The output request class for the Triton client.
        input_formats (List[str]): The data types of the model inputs.
        np_input_formats (List[type]): The numpy data types of the model inputs.
        input_names (List[str]): The names of the model inputs.
        output_names (List[str]): The names of the model outputs.
    '''

    def __init__(self, url: str, endpoint: str='', scheme: str=''):
        '''
        Initialize the TritonRemoteModel.
        Arguments may be provided individually or parsed from a collective 'url' argument of the form
            <scheme>://<netloc>/<endpoint>/<task_name>
        Args:
            url (str): The URL of the Triton server.
            endpoint (str): The name of the model on the Triton server.
            scheme (str): The communication scheme ('http' or 'grpc').
        '''
        pass

    def __call__(self, *inputs: np.ndarray) -> List[np.ndarray]:
        '''
        Call the model with the given inputs.
        Args:
            *inputs (List[np.ndarray]): Input data to the model.
        Returns:
            (List[np.ndarray]): Model outputs.
        '''
        pass
```

**Rewrite**

```python

class TritonRemoteModel:
    '''
    A client for remote model inference via the Triton Inference Server.
    Attributes:
        endpoint: The name of the model on the Triton server, as a string.
        url: The URL of the Triton server, as a string.
        triton_client: An instance of the Triton client, which is either an HTTP or gRPC client.
        InferInput: The class used to represent input data for the Triton client.
        InferRequestedOutput: The class used to represent output requests for the Triton client.
        input_formats: A list of strings enumerating the data types of the model inputs.
        np_input_formats: A list of numpy data types corresponding to the model inputs.
        input_names: A list of strings containing the names of the model inputs.
        output_names: A list of strings containing the names of the model outputs.
    '''

    def __init__(self, url: str, endpoint: str='', scheme: str=''):
        '''
        This method initializes an instance of the TritonRemoteModel class. Initialization parameters may be supplied as individual arguments or extracted from a single 'url' string in the format <scheme>://<netloc>/<endpoint>/<task_name>.
        Args:
            url: A string representing the URL of the Triton server.
            endpoint: A string representing the name of the model on the Triton server.
            scheme: A string that is either 'http' or 'grpc', specifying the communication scheme.
        '''
        pass

    def __call__(self, *inputs: np.ndarray) -> List[np.ndarray]:
        '''
        This method invokes the model with the provided input arguments.
        Args:
            *inputs: Input data provided as a list of numpy arrays.
        Returns:
            A list of numpy arrays representing the model outputs.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases all docstrings with equivalent technical meaning and requirements without altering types, behaviors, or specifications._

---

## 64. RealClassEval/post_cut-off/snippet_227 — `llm_lexical_01` (lexical)

**Original**

```python
class ConversationTurn:
    '''Represents a single turn in the conversation.'''

    def __init__(self, user_message, message_index):
        '''
        Initialize a conversation turn.
        Args:
            user_message: The user's message
            assistant_response: The assistant's response
            message_index: The index of the last message in this turn
        '''
        pass

    def _extract_preview(self, message, max_length=50):
        '''Extract a preview of the message for display in completions.'''
        pass

    def get_preview(self, max_length=50):
        '''Get a preview of the user message for display in completions.'''
        pass
```

**Rewrite**

```python
class ConversationTurn:
    '''Describes one exchange within a conversational dialogue.'''

    def __init__(self, user_message, message_index):
        '''
        Creates an instance representing a single turn in the conversation.
        Args:
            user_message: The user's message
            assistant_response: The assistant's response
            message_index: The index of the last message in this turn
        '''
        pass

    def _extract_preview(self, message, max_length=50):
        '''Generates a truncated excerpt of the message for autocomplete display purposes.'''
        pass

    def get_preview(self, max_length=50):
        '''Returns a shortened preview of the user's input message intended for completion suggestions.'''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and more descriptive terms without changing functional requirements, argument meanings, or behavior._

---

## 65. RealClassEval/post_cut-off/snippet_298 — `llm_formal_01` (formal)

**Original**

```python

class SessionManagerPort:
    '''Interface for SQLAlchemy session management operations.
    This interface defines the contract for session management adapters,
    providing methods for retrieving and managing database sessions
    in a synchronous context.
    Implementing classes must provide mechanisms to:
    1. Retrieve a properly configured SQLAlchemy session
    2. Release/remove sessions when they're no longer needed
    '''
    @abstractmethod
    def get_session(self) -> Session:
        '''Retrieve a SQLAlchemy session.
        This method provides a database session that can be used for
        querying, creating, updating, and deleting data.
        Returns:
            Session: A SQLAlchemy session object
        Examples:
            >>> session = session_manager.get_session()
            >>> results = session.query(User).all()
        '''
        pass
    @abstractmethod
    def remove_session(self) -> None:
        '''Remove the current session from the registry.
        This method should be called to clean up the session when it's
        no longer needed, helping to prevent resource leaks and ensure
        proper session management.
        '''
        pass
```

**Rewrite**

```python

class SessionManagerPort:
    '''The interface defines the contract for session management adapters. It provides methods for retrieving and managing database sessions within a synchronous context. Implementing classes are required to provide mechanisms for:
    1. retrieving a properly configured SQLAlchemy session
    2. releasing or removing sessions when they are no longer needed
    '''
    @abstractmethod
    def get_session(self) -> Session:
        '''A SQLAlchemy session is provided by the method. A database session that may be used for querying, creating, updating, and deleting data is returned. A SQLAlchemy session object is returned.
        Examples:
            >>> session = session_manager.get_session()
            >>> results = session.query(User).all()
        '''
        pass
    @abstractmethod
    def remove_session(self) -> None:
        '''The current session is removed from the registry. The method should be invoked to clean up the session when it is no longer needed, thereby preventing resource leaks and ensuring proper session management.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing (e.g., "must" vs "are required", "can be used" vs "may be used") and identical examples without changing any functional requirements, types, or behaviors._

---

## 66. RealClassEval/csn/snippet_109 — `llm_lexical_01` (lexical)

**Original**

```python

class HistoryManager:
    '''
    Define a base context manager.
    It records a list of actions to be taken at a later time.
    This is used to implement context managers that allow temporary
    changes to a `cobra.core.Model`.
    '''

    def __init__(self, **kwargs) -> None:
        '''Initialize the class.'''
        pass

    def __call__(self, operation: Callable[[Any], Any]) -> None:
        '''Add the corresponding operation to the history stack.
        Parameters
        ----------
        operation : callable
            A function to be called at a later time.
        '''
        pass

    def reset(self) -> None:
        '''Trigger executions for all items in the stack in reverse order.'''
        pass

    def size(self) -> int:
        '''Calculate number of operations on the stack.'''
        pass
```

**Rewrite**

```python

class HistoryManager:
    '''
    Serves as a foundational context manager implementation.
    It maintains a queue of operations designated for deferred execution.
    This design enables context managers to temporarily alter `cobra.core.Model` instances.
    '''

    def __init__(self, **kwargs) -> None:
        '''Executes initialization procedures for the class.'''
        pass

    def __call__(self, operation: Callable[[Any], Any]) -> None:
        '''Appends the appropriate operation to the history stack for future invocation.
        Parameters
        ----------
        operation : callable
            A function scheduled for later execution.
        '''
        pass

    def reset(self) -> None:
        '''Invokes all entries in the stack sequentially from last-added to first.'''
        pass

    def size(self) -> int:
        '''Computes the total count of operations stored within the stack.'''
        pass
```

_judge: EQUIVALENT — The method docstrings specify identical LIFO stack behavior for operations, and the class docstring terminology change from "list" to "queue" (despite the latter typically implying FIFO) does not alter the defined execution requirements._

---

## 67. RealClassEval/post_cut-off/snippet_97 — `llm_formal_01` (formal)

**Original**

```python

class GCPRegions:
    '''
    A class for managing and analyzing Google Cloud Platform (GCP) regions.
    This class provides functionality to initialize, categorize, and analyze GCP regions based on their
    geographical location, tier classification, and network latency.
    Attributes:
        regions (Dict[str, Tuple[int, str, str]]): A dictionary of GCP regions with their tier, city, and country.
    Methods:
        tier1: Returns a list of tier 1 GCP regions.
        tier2: Returns a list of tier 2 GCP regions.
        lowest_latency: Determines the GCP region(s) with the lowest network latency.
    Examples:
        >>> from ultralytics.hub.google import GCPRegions
        >>> regions = GCPRegions()
        >>> lowest_latency_region = regions.lowest_latency(verbose=True, attempts=3)
        >>> print(f"Lowest latency region: {lowest_latency_region[0][0]}")
    '''

    def __init__(self):
        '''Initializes the GCPRegions class with predefined Google Cloud Platform regions and their details.'''
        pass

    def tier1(self) -> List[str]:
        '''Returns a list of GCP regions classified as tier 1 based on predefined criteria.'''
        pass

    def tier2(self) -> List[str]:
        '''Returns a list of GCP regions classified as tier 2 based on predefined criteria.'''
        pass
    @staticmethod
    def _ping_region(region: str, attempts: int=1) -> Tuple[str, float, float, float, float]:
        '''Pings a specified GCP region and returns latency statistics: mean, min, max, and standard deviation.'''
        pass

    def lowest_latency(self, top: int=1, verbose: bool=False, tier: Optional[int]=None, attempts: int=1) -> List[Tuple[str, float, float, float, float]]:
        '''
        Determines the GCP regions with the lowest latency based on ping tests.
        Args:
            top (int): Number of top regions to return.
            verbose (bool): If True, prints detailed latency information for all tested regions.
            tier (int | None): Filter regions by tier (1 or 2). If None, all regions are tested.
            attempts (int): Number of ping attempts per region.
        Returns:
            (List[Tuple[str, float, float, float, float]]): List of tuples containing region information and
            latency statistics. Each tuple contains (region, mean_latency, std_dev, min_latency, max_latency).
        Examples:
            >>> regions = GCPRegions()
            >>> results = regions.lowest_latency(top=3, verbose=True, tier=1, attempts=2)
            >>> print(results[0][0])  # Print the name of the lowest latency region
        '''
        pass
```

**Rewrite**

```python

class GCPRegions:
    '''
    This class provides functionality for initializing, categorizing, and analyzing Google Cloud Platform (GCP) regions based on geographical location, tier classification, and network latency.
    The 'regions' attribute is a dictionary mapping region names (strings) to tuples containing the tier (integer), city (string), and country (string) for each GCP region.
    The 'tier1' method returns a list of GCP region identifiers classified as tier 1 based on predefined criteria.
    The 'tier2' method returns a list of GCP region identifiers classified as tier 2 based on predefined criteria.
    The 'lowest_latency' method returns a list of GCP region identifiers for the region(s) with the lowest network latency based on ping test results.
    Examples:
    >>> from ultralytics.hub.google import GCPRegions
    >>> regions = GCPRegions()
    >>> lowest_latency_region = regions.lowest_latency(verbose=True, attempts=3)
    >>> print(f"Lowest latency region: {lowest_latency_region[0][0]}")
    '''

    def __init__(self):
        '''The GCPRegions class instance is initialized with predefined Google Cloud Platform (GCP) region data.'''
        pass

    def tier1(self) -> List[str]:
        '''The 'tier1' method returns a list of GCP region identifiers classified as tier 1 according to predefined criteria.'''
        pass

    def tier2(self) -> List[str]:
        '''The 'tier2' method returns a list of GCP region identifiers classified as tier 2 according to predefined criteria.'''
        pass
    @staticmethod
    def _ping_region(region: str, attempts: int=1) -> Tuple[str, float, float, float, float]:
        '''The '_ping_region' static method pings a specified GCP region and returns latency statistics including the mean, minimum, maximum, and standard deviation of the ping measurements.'''
        pass

    def lowest_latency(self, top: int=1, verbose: bool=False, tier: Optional[int]=None, attempts: int=1) -> List[Tuple[str, float, float, float, float]]:
        '''
        The 'lowest_latency' method identifies GCP regions with the lowest network latency based on ping test results.
        Args:
            top: An integer specifying the number of top regions to return.
            verbose: A boolean value; if true, detailed latency information for all tested regions is printed.
            tier: An optional integer (1 or 2) specifying the tier filter; if none, all regions are considered.
            attempts: An integer specifying the number of ping attempts per region.
        Returns:
            A list of tuples, each tuple containing the following elements in order: a GCP region identifier (string), the mean latency (float), the standard deviation of latency (float), the minimum latency (float), and the maximum latency (float).
        Examples:
        >>> regions = GCPRegions()
        >>> results = regions.lowest_latency(top=3, verbose=True, tier=1, attempts=2)
        >>> print(results[0][0])  # Print the name of the lowest latency region
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification rephrases all docstrings without changing the meaning of requirements, arguments, attributes, return values, or examples._

---

## 68. RealClassEval/post_cut-off/snippet_302 — `llm_lexical_01` (lexical)

**Original**

```python

class KafkaProducerPort:
    '''Interface for Kafka producer operations.
    This interface defines the contract for producing messages to Kafka topics.
        '''
    @abstractmethod
    def produce(self, message: str | bytes) -> None:
        '''Produces a message to the configured topic.
        Args:
            message (str | bytes): The message to produce.
        Raises:
            NotImplementedError: If the method is not implemented by the concrete class.
        '''
        pass
    @abstractmethod
    def flush(self, timeout: int | None) -> None:
        '''Flushes any pending messages to the broker.
        Args:
            timeout (int | None): Maximum time to wait for messages to be delivered.
                If None, wait indefinitely.
        Raises:
            NotImplementedError: If the method is not implemented by the concrete class.
        '''
        pass
    @abstractmethod
    def validate_healthiness(self) -> None:
        '''Validates the health of the producer connection.
        Raises:
            NotImplementedError: If the method is not implemented by the concrete class.
        '''
        pass
    @abstractmethod
    def list_topics(self, topic: str | None, timeout: int) -> ClusterMetadata:
        '''Lists Kafka topics.
        Args:
            topic (str | None): Specific topic to list. If None, lists all topics.
            timeout (int): Timeout in seconds for the operation.
        Returns:
            ClusterMetadata: Metadata about the Kafka cluster and topics.
        Raises:
            NotImplementedError: If the method is not implemented by the concrete class.
        '''
        pass
```

**Rewrite**

```python

class KafkaProducerPort:
    '''Contract establishing the operational agreement for publishing messages to Kafka topics.
        '''
    @abstractmethod
    def produce(self, message: str | bytes) -> None:
        '''Sends a message to the pre-configured Kafka topic.
        Args:
            message (str | bytes): The message payload intended for transmission.
        Raises:
            NotImplementedError: If the concrete implementation lacks this functionality.
        '''
        pass
    @abstractmethod
    def flush(self, timeout: int | None) -> None:
        '''Dispatches all queued messages to the Kafka broker.
        Args:
            timeout (int | None): Maximum wait duration in seconds for delivery completion.
                If None, block indefinitely.
        Raises:
            NotImplementedError: If the concrete implementation omits this method.
        '''
        pass
    @abstractmethod
    def validate_healthiness(self) -> None:
        '''Verifies the operational status of the producer's network connection.
        Raises:
            NotImplementedError: If the concrete implementation does not provide this check.
        '''
        pass
    @abstractmethod
    def list_topics(self, topic: str | None, timeout: int) -> ClusterMetadata:
        '''Retrieves available Kafka topics within the cluster.
        Args:
            topic (str | None): Specific topic identifier; omitting lists all topics.
            timeout (int): Allotted seconds for completing the topic enumeration.
        Returns:
            ClusterMetadata: Details regarding cluster configuration and topic inventory.
        Raises:
            NotImplementedError: If the concrete implementation fails to realize this method.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing (e.g., "Sends" vs "Produces", "Dispatches" vs "Flushes") without changing any technical requirements, types, arguments, return values, or behavioral semantics._

---

## 69. RealClassEval/post_cut-off/snippet_253 — `llm_formal_01` (formal)

**Original**

```python

class PromptLogger:
    '''提示词日志记录器'''

    def __init__(self, log_file: str='log.txt'):
        '''
        初始化日志记录器
        参数:
            log_file: 日志文件路径
        '''
        pass

    def log_prompt(self, messages: List[Dict[str, str]], character_name: str=None, user_query: str=None):
        '''
        记录完整的提示词到日志文件
        参数:
            messages: 发送给模型的消息列表
            character_name: 角色名称
            user_query: 用户查询（原始请求）
        '''
        pass

    def log_formatted_prompt(self, system_prompt: str, user_prompt: str, memory_context: str='', character_name: str=None, user_query: str=None):
        '''
        记录格式化的提示词（分别记录system和user部分）
        参数:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            memory_context: 记忆上下文
            character_name: 角色名称
            user_query: 原始用户查询（未经任何加工的用户输入）
        '''
        pass

    def get_recent_logs(self, count: int=10) -> List[Dict]:
        '''
        获取最近的日志条目
        参数:
            count: 返回的条目数量
        返回:
            最近的日志条目列表
        '''
        pass

    def clear_logs(self):
        '''清空日志文件'''
        pass
```

**Rewrite**

```python

class PromptLogger:
    '''Prompt Logger'''

    def __init__(self, log_file: str='log.txt'):
        '''
        Initializes the prompt logger.
        Parameters:
            log_file: path to the log file
        '''
        pass

    def log_prompt(self, messages: List[Dict[str, str]], character_name: str=None, user_query: str=None):
        '''
        Records the complete prompt to the log file.
        Parameters:
            messages: list of messages sent to the model
            character_name: name of the character
            user_query: original user query
        '''
        pass

    def log_formatted_prompt(self, system_prompt: str, user_prompt: str, memory_context: str='', character_name: str=None, user_query: str=None):
        '''
        Records the formatted prompt, separately logging the system and user sections.
        Parameters:
            system_prompt: system prompt
            user_prompt: user prompt
            memory_context: memory context
            character_name: name of the character
            user_query: original user query
        '''
        pass

    def get_recent_logs(self, count: int=10) -> List[Dict]:
        '''
        Retrieves the most recent log entries.
        Parameters:
            count: number of log entries to return
        Returns:
            list of the most recent log entries
        '''
        pass

    def clear_logs(self):
        '''Clears the log file.'''
        pass
```

_judge: EQUIVALENT — The English rewrite accurately translates all parameter descriptions and behavioral requirements without altering types, meanings, or examples._

---

## 70. RealClassEval/csn/snippet_252 — `llm_lexical_01` (lexical)

**Original**

```python
class RGB888Format:
    '''RGB888Format'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Set a given pixel to a color.'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Get the color of a given pixel'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''completely fill/clear the buffer with a color'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''Draw a rectangle at the given location, size and color. The ``fill_rect`` method draws
        both the outline and interior.'''
        pass
```

**Rewrite**

```python
class RGB888Format:
    '''Represents the RGB888 color format for frame buffer operations.'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Sets the color value for the pixel at the specified x and y coordinates.'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Retrieves the color value of the pixel located at the given x and y position.'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''Fills the entire frame buffer with the specified color, effectively erasing prior content.'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''Fills a rectangular area defined by top-left corner (x, y), width, and height using the given color, rendering both the boundary and filled interior.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use more precise terminology (e.g., "coordinates" instead of "pixel", "value" instead of "color") but describe identical requirements for all methods without altering behavior, parameters, or examples._

---

## 71. RealClassEval/csn/snippet_50 — `llm_lexical_01` (lexical)

**Original**

```python
class MetPyChecker:
    '''Flake8 plugin class to check MetPy style/best practice.'''

    def __init__(self, tree):
        '''Initialize the plugin.'''
        pass

    def run(self):
        '''Run the plugin and yield errors.'''
        pass

    def error(self, err):
        '''Format errors into Flake8's required format.'''
        pass
```

**Rewrite**

```python
class MetPyChecker:
    '''A Flake8 plugin class for verifying MetPy style and best practice adherence.'''

    def __init__(self, tree):
        '''Set up the plugin instance.'''
        pass

    def run(self):
        '''Execute the plugin and yield individual error reports.'''
        pass

    def error(self, err):
        '''Convert errors to Flake8's mandated error reporting format.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing (e.g., "verifying" vs "check", "individual error reports" vs "errors") without changing any functional requirements, types, or behaviors._

---

## 72. RealClassEval/post_cut-off/snippet_362 — `llm_lexical_01` (lexical)

**Original**

```python

class ScriptRunner:
    '''Executes APM scripts with auto-compilation of .prompt.md files.'''

    def __init__(self, compiler=None):
        '''Initialize script runner with optional compiler.'''
        pass

    def run_script(self, script_name: str, params: Dict[str, str]) -> bool:
        '''Run a script from apm.yml with parameter substitution.
        Args:
            script_name: Name of the script to run
            params: Parameters for compilation and script execution
        Returns:
            bool: True if script executed successfully
        '''
        pass

    def list_scripts(self) -> Dict[str, str]:
        '''List all available scripts from apm.yml.
        Returns:
            Dict mapping script names to their commands
        '''
        pass

    def _load_config(self) -> Optional[Dict]:
        '''Load apm.yml from current directory.'''
        pass

    def _auto_compile_prompts(self, command: str, params: Dict[str, str]) -> tuple[str, list[str]]:
        '''Auto-compile .prompt.md files and transform runtime commands.
        Args:
            command: Original script command
            params: Parameters for compilation
        Returns:
            Tuple of (compiled_command, list_of_compiled_prompt_files)
        '''
        pass

    def _transform_runtime_command(self, command: str, prompt_file: str, compiled_content: str, compiled_path: str) -> str:
        '''Transform runtime commands to their proper execution format.
        Args:
            command: Original command
            prompt_file: Original .prompt.md file path
            compiled_content: Compiled prompt content as string
            compiled_path: Path to compiled .txt file
        Returns:
            Transformed command for proper runtime execution
        '''
        pass
```

**Rewrite**

```python

class ScriptRunner:
    '''Runs APM scripts by automatically compiling .prompt.md files.'''

    def __init__(self, compiler=None):
        '''Sets up the script runner using an optional compiler.'''
        pass

    def run_script(self, script_name: str, params: Dict[str, str]) -> bool:
        '''Execute a script defined in apm.yml through parameter substitution.
        Args:
            script_name: Name of the script to execute
            params: Values provided for compilation and script operation
        Returns:
            bool: True if the script runs without errors
        '''
        pass

    def list_scripts(self) -> Dict[str, str]:
        '''Retrieve all scripts listed in apm.yml.
        Returns:
            Dict linking script names to their command strings
        '''
        pass

    def _load_config(self) -> Optional[Dict]:
        '''Load the apm.yml configuration file from the current directory.'''
        pass

    def _auto_compile_prompts(self, command: str, params: Dict[str, str]) -> tuple[str, list[str]]:
        '''Automatically convert .prompt.md files and adjust runtime commands.
        Args:
            command: Original script command string
            params: Parameters used during compilation
        Returns:
            Tuple containing (final execution command, list of compiled prompt files)
        '''
        pass

    def _transform_runtime_command(self, command: str, prompt_file: str, compiled_content: str, compiled_path: str) -> str:
        '''Convert runtime commands into the correct format for execution.
        Args:
            command: Initial command string
            prompt_file: Path to the source .prompt.md file
            compiled_content: Compiled prompt text as string
            compiled_path: Location of the generated .txt file
        Returns:
            Transformed command ready for runtime invocation
        '''
        pass
```

_judge: EQUIVALENT — All docstring changes use synonymous phrasing without altering the meaning of requirements, types, or behaviors._

---

## 73. RealClassEval/csn/snippet_82 — `llm_lexical_01` (lexical)

**Original**

```python

class Completer:
    '''base class for completers'''
    @abc.abstractmethod
    def complete(self, original, pos):
        '''returns a list of completions and cursor positions for the string
        `original` from position `pos` on.
        :param original: the string to complete
        :type original: str
        :param pos: starting position to complete from
        :type pos: int
        :returns: pairs of completed string and cursor position in the
                  new string
        :rtype: list of (str, int)
        :raises: :exc:`CompletionError`
        '''
        pass

    def relevant_part(self, original, pos):
        '''
        Calculate the subword in a ' '-separated list of substrings of
        `original` that `pos` is in.
        '''
        pass
```

**Rewrite**

```python

class Completer:
    '''foundational abstract base class for completion functionality'''
    @abc.abstractmethod
    def complete(self, original, pos):
        '''Provides a collection of text completion proposals paired with their corresponding cursor offsets for the input string `original` beginning at index `pos`.
        :param original: the string requiring completion suggestions
        :type original: str
        :param pos: the index within the string where completion should commence
        :type pos: int
        :returns: sequence of tuples each containing a fully completed string and the updated cursor position in that string
        :rtype: list of (str, int)
        :raises: :exc:`CompletionError` if completion cannot be processed
        '''
        pass

    def relevant_part(self, original, pos):
        '''
        Determine which space-delimited token in `original` contains the character at index `pos`
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases requirements with synonymous terms (e.g., "list of completions" → "collection of text completion proposals") and clarifies exception conditions without altering the core behavior or specifications._

---

## 74. RealClassEval/post_cut-off/snippet_57 — `llm_formal_01` (formal)

**Original**

```python

class FFTConvolution:
    '''
    Initial implementation of fft_convolution task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the FFTConvolution.'''
        pass

    def solve(self, problem):
        '''
        Solve the fft_convolution problem.
        Args:
            problem: Dictionary containing problem data specific to fft_convolution
        Returns:
            The solution in the format expected by the task
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Check if the provided solution is valid.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

**Rewrite**

```python

class FFTConvolution:
    '''
    The initial implementation of the fft_convolution task is provided. This implementation will be evolved by the OpenEvolve framework for the purpose of improving performance and correctness.
    '''

    def __init__(self):
        '''Instantiate the FFTConvolution class.'''
        pass

    def solve(self, problem):
        '''
        Solve the fft_convolution problem.
        Args:
            problem: A dictionary containing problem data specific to fft_convolution.
        Returns:
            The solution in the format expected by the task.
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Verify the validity of the proposed solution for the original problem.
        Args:
            problem: The original problem.
            solution: The proposed solution for the problem.
        Returns:
            True if the solution is valid for the original problem, otherwise False.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing and clarifies the scope of `is_solution` without altering requirements, types, arguments, return values, or behavior._

---

## 75. RealClassEval/post_cut-off/snippet_211 — `llm_terse_01` (terse)

**Original**

```python

class ErrorHandler:
    '''
    Centralized error handling system for the PCILeech TUI application.
    This class provides a consistent way to handle errors throughout the application,
    including logging, user notifications, and critical error reporting.
    '''

    def __init__(self, app):
        '''
        Initialize the error handler with the app instance.
        Args:
            app: The main TUI application instance
        '''
        pass

    def handle_error(self, error: Exception, context: str, severity: str='error') -> None:
        '''
        Centralized error handling with context
        Args:
            error: The exception that occurred
            context: Description of where/when the error occurred
            severity: Error severity level ("error", "warning", "critical")
        '''
        pass

    def handle_operation_error(self, operation: str, error: Exception, severity: str='error') -> None:
        '''
        Handle errors that occur during specific operations with a standard format.
        Args:
            operation: The operation that failed (e.g., "scanning devices", "starting build")
            error: The exception that occurred
            severity: Error severity level ("error", "warning", "critical")
        '''
        pass

    def _get_user_friendly_message(self, error: Exception, context: str) -> str:
        '''
        Generate a user-friendly error message based on the exception type and context.
        Args:
            error: The exception that occurred
            context: Description of where/when the error occurred
        Returns:
            A user-friendly error message
        '''
        pass

    def _report_critical_error(self, error: Exception, context: str) -> None:
        '''
        Report critical errors for later analysis or immediate attention.
        Args:
            error: The exception that occurred
            context: Description of where/when the error occurred
        '''
        pass

    def _write_traceback_to_file(self, context: str, tb_str: str) -> None:
        '''Append a timestamped traceback to the persistent error log.
        The log is stored under `logs/error.log` relative to the repository root.
        '''
        pass
```

**Rewrite**

```python

class ErrorHandler:
    '''
    PCILeech TUI error handling: logging, notifications, critical reporting
    '''

    def __init__(self, app):
        '''
        Args:
        app: TUI
        '''
        pass

    def handle_error(self, error: Exception, context: str, severity: str='error') -> None:
        '''
        Handle errors with context
        Args:
        error: Exception
        context: Location/when
        severity: error, warning, critical
        '''
        pass

    def handle_operation_error(self, operation: str, error: Exception, severity: str='error') -> None:
        '''
        Handle operation errors with standard format
        Args:
        operation: Operation
        error: Exception
        severity: error, warning, critical
        '''
        pass

    def _get_user_friendly_message(self, error: Exception, context: str) -> str:
        '''
        Generate user-friendly message from exception and context
        Args:
        error: Exception
        context: Location/when
        Returns: User-friendly message
        '''
        pass

    def _report_critical_error(self, error: Exception, context: str) -> None:
        '''
        Report critical errors for analysis/attention
        Args:
        error: Exception
        context: Location/when
        '''
        pass

    def _write_traceback_to_file(self, context: str, tb_str: str) -> None:
        '''Append timestamped traceback to persistent error log
        Location: logs/error.log (relative to repository root)
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases docstrings and argument descriptions using synonymous terms without changing functional requirements, examples, or behavior._

---

## 76. RealClassEval/csn/snippet_106 — `llm_formal_01` (formal)

**Original**

```python
class XMLStorage:
    '''Generic class for storing XML data from PLIP XML files.'''
    @staticmethod
    def getdata(tree, location, force_string=False):
        '''Gets XML data from a specific element and handles types.'''
        pass
    @staticmethod
    def getcoordinates(tree, location):
        '''Gets coordinates from a specific element in PLIP XML'''
        pass
```

**Rewrite**

```python
class XMLStorage:
    '''Provides generic storage functionality for XML data originating from PLIP XML files.'''
    @staticmethod
    def getdata(tree, location, force_string=False):
        '''Retrieves XML data from a specified element within a PLIP XML document and manages data type conversion.'''
        pass
    @staticmethod
    def getcoordinates(tree, location):
        '''Extracts coordinate data from a designated element within a PLIP XML document.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing (e.g., "Retrieves" vs "Gets", "manages data type conversion" vs "handles types") without changing the core requirements, argument meanings, or behavior specifications._

---

## 77. RealClassEval/csn/snippet_260 — `llm_formal_01` (formal)

**Original**

```python
class Pattern:
    '''A single pattern for either inclusion or exclusion.'''

    def __init__(self, spec, inclusive):
        '''Create regex-based pattern matcher from glob `spec`.'''
        pass

    def __str__(self):
        '''Return inclusiveness indicator and original glob pattern.'''
        pass

    def matches(self, path):
        '''Check this pattern against given `path`.'''
        pass
```

**Rewrite**

```python
class Pattern:
    '''Represents a pattern for inclusion or exclusion.'''

    def __init__(self, spec, inclusive):
        '''A regex-based pattern matcher is constructed from the glob pattern `spec`.'''
        pass

    def __str__(self):
        '''The inclusiveness indicator and the original glob pattern string are returned.'''
        pass

    def matches(self, path):
        '''The provided path is checked against the pattern for a match.'''
        pass
```

_judge: EQUIVALENT — The rewrite only rephrases requirements with passive voice or minor clarifications (e.g., adding "string") without changing any functional behavior, types, or conditions._

---

## 78. RealClassEval/post_cut-off/snippet_346 — `llm_formal_01` (formal)

**Original**

```python

class EventDataNormalizer:
    '''事件数据标准化器'''
    @staticmethod
    def normalize_event_data(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        '''标准化事件数据格式'''
        pass
    @staticmethod
    def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
        '''从事件数据中提取用户ID'''
        pass
    @staticmethod
    def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
        '''从事件数据中提取目标信息，返回(target_id, is_group)'''
        pass
```

**Rewrite**

```python

class EventDataNormalizer:
    '''Utility class providing static methods for event data normalization.'''
    @staticmethod
    def normalize_event_data(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        '''The event data format is standardized.'''
        pass
    @staticmethod
    def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
        '''The user identifier is extracted from the event data.'''
        pass
    @staticmethod
    def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
        '''Target information, consisting of a target identifier and a boolean indicating group membership, is extracted from the event data.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using equivalent meaning without altering types, behaviors, or adding/removing specifications._

---

## 79. RealClassEval/post_cut-off/snippet_289 — `llm_formal_01` (formal)

**Original**

```python
@dataclass
class UpdateRuleDeployment:
    '''Model for updating rule deployment.'''

    def __post_init__(self):
        '''Post initilizaiton for validating/converting attributes'''
        pass

    def to_dict(self) -> Dict[str, Any]:
        '''Convert to dictionary for JSON serialization.'''
        pass
```

**Rewrite**

```python
@dataclass
class UpdateRuleDeployment:
    '''The model for an update rule deployment is defined by this dataclass.'''

    def __post_init__(self):
        '''The __post_init__ method is executed after dataclass initialization to validate and convert attributes.'''
        pass

    def to_dict(self) -> Dict[str, Any]:
        '''The to_dict method converts the instance to a dictionary for JSON serialization.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using explanatory language without altering any functional behavior, validation rules, or serialization semantics._

---

## 80. RealClassEval/csn/snippet_42 — `llm_terse_01` (terse)

**Original**

```python

class WifiManager:
    '''
    Simulates Android WifiManager.
    @see: http://developer.android.com/reference/android/net/wifi/WifiManager.html
    '''

    def __init__(self, device):
        '''
        Constructor.
        :param device:
        :type device:
        '''
        pass

    def getWifiState(self):
        '''
        Gets the Wi-Fi enabled state.
        @return: One of WIFI_STATE_DISABLED, WIFI_STATE_DISABLING, WIFI_STATE_ENABLED, WIFI_STATE_ENABLING, WIFI_STATE_UNKNOWN
        '''
        pass
```

**Rewrite**

```python

class WifiManager:
    '''
    Android WifiManager simulator @see: http://developer.android.com/reference/android/net/wifi/WifiManager.html
    '''

    def __init__(self, device):
        '''
        Constructor
        :param device
        :type device
        '''
        pass

    def getWifiState(self):
        '''
        Gets Wi-Fi enabled state
        @return: WIFI_STATE_DISABLED, WIFI_STATE_DISABLING, WIFI_STATE_ENABLED, WIFI_STATE_ENABLING, WIFI_STATE_UNKNOWN
        '''
        pass
```

_judge: EQUIVALENT — The rewrite only changes minor wording and punctuation in docstrings without altering any functional requirements, parameter types, return values, or examples._

---

## 81. RealClassEval/csn/snippet_147 — `llm_terse_01` (terse)

**Original**

```python
class NoHashContext:
    '''No-op hash function.'''

    def __init__(self, data=None):
        '''Initialize'''
        pass

    def update(self, data):
        '''Update data'''
        pass

    def digest(self):
        '''Final hash'''
        pass

    def hexdigest(self):
        '''Hexadecimal digest.'''
        pass
```

**Rewrite**

```python
class NoHashContext:
    '''No-op hash function'''

    def __init__(self, data=None):
        '''Initialize'''
        pass

    def update(self, data):
        '''Update data'''
        pass

    def digest(self):
        '''Final hash'''
        pass

    def hexdigest(self):
        '''Hex digest'''
        pass
```

_judge: EQUIVALENT — The change from "Hexadecimal digest." to "Hex digest" abbreviates the term without altering the requirement for a hexadecimal string return value._

---

## 82. RealClassEval/csn/snippet_142 — `llm_terse_01` (terse)

**Original**

```python
class ProjectTemplate:
    ''' Public data which can be set in yaml files
        Yaml data available are:
            'build_dir' : build_dir,    # Build output path
            'debugger' : debugger,      # Debugger
            'export_dir': '',           # Export directory path
            'includes': [],             # include paths
            'linker_file': None,        # linker script file
            'name': name,               # project name
            'macros': [],               # macros
            'misc': {},                 # misc settings related to tools
            'output_type': output_type, # output type, default - exe
            'sources': [],              # source files/folders
            'target': '',               # target
            'template' : [],            # tool template
            'tools_supported': [],      # Tools which are supported,
    '''
    @staticmethod
    def _get_common_data_template():
        ''' Data for tool specific '''
        pass
    @staticmethod
    def _get_tool_specific_data_template():
        ''' Data for tool specific '''
        pass
    @staticmethod
    def get_project_template(name='Default', output_type='exe', debugger=None, build_dir='build'):
        ''' Project data (+ data) '''
        pass
```

**Rewrite**

```python
class ProjectTemplate:
    ''' Public YAML settings
        'build_dir' : build_dir,    # Build output path
        'debugger' : debugger,      # Debugger
        'export_dir': '',           # Export directory path
        'includes': [],             # include paths
        'linker_file': None,        # linker script file
        'name': name,               # project name
        'macros': [],               # macros
        'misc': {},                 # misc settings related to tools
        'output_type': output_type, # output type, default - exe
        'sources': [],              # source files/folders
        'target': '',               # target
        'template' : [],            # tool template
        'tools_supported': [],      # Tools which are supported,
    '''
    @staticmethod
    def _get_common_data_template():
        ''' Tool-specific data '''
        pass
    @staticmethod
    def _get_tool_specific_data_template():
        ''' Tool-specific data '''
        pass
    @staticmethod
    def get_project_template(name='Default', output_type='exe', debugger=None, build_dir='build'):
        ''' Project data '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases docstring wording (e.g., "Public data which can be set in yaml files" → "Public YAML settings", "Data for tool specific" → "Tool-specific data", "Project data (+ data)" → "Project data") without altering any technical requirements, argument types, or behavioral semantics._

---

## 83. RealClassEval/csn/snippet_120 — `llm_formal_01` (formal)

**Original**

```python
class NestedDummyClass:
    '''Nested dummy class for testing method resolution.'''

    def run(self):
        '''Do nothing.'''
        pass
    @property
    def prop(self):
        '''Property.'''
        pass
```

**Rewrite**

```python
class NestedDummyClass:
    '''A nested dummy class used for testing method resolution.'''

    def run(self):
        '''No operation is performed by the method.'''
        pass
    @property
    def prop(self):
        '''A property of the class.'''
        pass
```

_judge: EQUIVALENT — The docstrings use synonymous phrasing without changing functional requirements, argument/attribute types, or behavior._

---

## 84. RealClassEval/csn/snippet_208 — `llm_terse_01` (terse)

**Original**

```python

class NullFile:
    '''A file object that is associated to /dev/null.'''

    def __new__(cls):
        '''
        Pass through.
        '''
        pass

    def __init__(self):
        '''no-op'''
        pass
```

**Rewrite**

```python

class NullFile:
    '''Devnull file'''

    def __new__(cls):
        '''
        Pass-through
        '''
        pass

    def __init__(self):
        '''no-op'''
        pass
```

_judge: EQUIVALENT — The changes are purely stylistic (e.g., "Pass through" vs. "Pass-through", "A file object that is associated to /dev/null" vs. "Devnull file") without altering any functional requirements, types, or behaviors._

---

## 85. RealClassEval/post_cut-off/snippet_201 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class OverridableConfig:
    '''A class that provides an interface to switch between its field values depending on an override key.'''

    def __post_init__(self) -> None:
        '''Initialize the override key to 'default'.'''
        pass

    def set_override(self, key: str, reset_to_defaults: bool=True) -> None:
        '''Set the overridden values for the config based on the override registry.
        Args:
            key: The key to use for the override.
            reset_to_defaults: If True, reset the values to their defaults if no override is found. This is useful for
                when you switch from different non-default overrides to other non-default overrides.
        '''
        pass
```

**Rewrite**

```python
@dataclass
class OverridableConfig:
    '''Config field values override switching.'''

    def __post_init__(self) -> None:
        '''Set override key to 'default'.'''
        pass

    def set_override(self, key: str, reset_to_defaults: bool=True) -> None:
        '''Update config from override registry.
        Args:
            key: Override key.
            reset_to_defaults: Reset defaults if no override; useful for non-default override switches.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite condenses docstring wording without changing requirements, types, or behaviors described._

---

## 86. RealClassEval/post_cut-off/snippet_23 — `llm_formal_01` (formal)

**Original**

```python

class GitHubURLExtractor:
    '''提取GitHub URL的工具类'''
    @staticmethod
    def extract_github_urls(text: str) -> List[str]:
        '''从文本中提取GitHub URLs'''
        pass
    @staticmethod
    def extract_target_path(text: str) -> Optional[str]:
        '''从文本中提取目标路径'''
        pass
    @staticmethod
    def infer_repo_name(url: str) -> str:
        '''从URL推断仓库名称'''
        pass
```

**Rewrite**

```python

class GitHubURLExtractor:
    '''Utility class for extracting GitHub Uniform Resource Locators.'''
    @staticmethod
    def extract_github_urls(text: str) -> List[str]:
        '''GitHub Uniform Resource Locators are extracted from text.'''
        pass
    @staticmethod
    def extract_target_path(text: str) -> Optional[str]:
        '''Target paths are extracted from text.'''
        pass
    @staticmethod
    def infer_repo_name(url: str) -> str:
        '''The repository name is inferred from the URL.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing and passive voice without changing the described behavior or requirements._

---

## 87. RealClassEval/post_cut-off/snippet_312 — `llm_lexical_01` (lexical)

**Original**

```python

class NotesSearchController:
    '''Handles notes search logic and scoring.'''

    def search_notes(self, notes: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        '''
        Search notes using token-based matching with relevance ranking.
        Returns notes sorted by relevance score.
        '''
        pass

    def _process_query(self, query: str) -> List[str]:
        '''
        Tokenize and normalize the search query.
        '''
        pass

    def _process_note_content(self, note: Dict[str, Any]) -> tuple[List[str], List[str]]:
        '''
        Tokenize and normalize note title and content.
        '''
        pass

    def _calculate_score(self, query_tokens: List[str], title_tokens: List[str], content_tokens: List[str]) -> float:
        '''
        Calculate a relevance score for a note based on query tokens.
        '''
        pass
```

**Rewrite**

```python

class NotesSearchController:
    '''Manages the functionality for searching through notes and computing their relevance scores.'''

    def search_notes(self, notes: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        '''
        Performs a search across notes via token matching and relevance-based ranking. The results are ordered according to their computed relevance scores.
        '''
        pass

    def _process_query(self, query: str) -> List[str]:
        '''
        Convert the search query into tokens and apply normalization.
        '''
        pass

    def _process_note_content(self, note: Dict[str, Any]) -> tuple[List[str], List[str]]:
        '''
        Process the note's title and content by tokenizing and normalizing them.
        '''
        pass

    def _calculate_score(self, query_tokens: List[str], title_tokens: List[str], content_tokens: List[str]) -> float:
        '''
        Determine a relevance score for a note using the tokens from the search query.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using synonymous language without changing any technical specifications, types, arguments, or behavior._

---

## 88. RealClassEval/post_cut-off/snippet_41 — `llm_lexical_01` (lexical)

**Original**

```python

class HeaderManager:
    '''Manager for header layout and formatting.'''

    def __init__(self) -> None:
        '''Initialize header manager.'''
        pass

    def create_header(self, plan: str='pro', timezone: str='Europe/Warsaw') -> list[str]:
        '''Create stylized header with sparkles.
        Args:
            plan: Current plan name
            timezone: Display timezone
        Returns:
            List of formatted header lines
        '''
        pass
```

**Rewrite**

```python

class HeaderManager:
    '''Coordinates header arrangement and presentation.'''

    def __init__(self) -> None:
        '''Sets up the header management system.'''
        pass

    def create_header(self, plan: str='pro', timezone: str='Europe/Warsaw') -> list[str]:
        '''Generates an embellished header with decorative sparkle elements.
        Parameters:
          plan: Name of the current plan
          timezone: Timezone for display
        Returns:
          List of strings holding formatted header lines
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing (e.g., "stylized" vs "embellished", "formatted header lines" vs "strings holding formatted header lines") without changing requirements, types, or behavior._

---

## 89. RealClassEval/csn/snippet_249 — `llm_lexical_01` (lexical)

**Original**

```python

class Template:
    '''Provide tool to managed templates
    '''

    def __init__(self):
        '''Class instantiation
        '''
        pass

    def render(self, sources, config, out=sys.stdout):
        '''Render the documentation as defined in config Object
        '''
        pass
```

**Rewrite**

```python

class Template:
    '''Offers a utility for template management.
    '''

    def __init__(self):
        '''Handles the creation of class instances.
        '''
        pass

    def render(self, sources, config, out=sys.stdout):
        '''Generates documentation as specified by the config object.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing without changing the described functionality or requirements._

---

## 90. RealClassEval/csn/snippet_28 — `llm_lexical_01` (lexical)

**Original**

```python
class DistanceData:
    '''
    Data structure for holding information about a distance query.
    '''

    def __init__(self, names, result):
        '''
        Initialize a DistanceData.
        Parameters
        ----------
        names : list of str
          The names of the two objects in order.
        contact : fcl.DistanceResult
          The distance query result.
        '''
        pass
    @property
    def distance(self):
        '''
        Returns the distance between the two objects.
        Returns
        -------
        distance : float
          The euclidean distance between the objects.
        '''
        pass

    def index(self, name):
        '''
        Returns the index of the closest face for the mesh with
        the given name.
        Parameters
        ----------
        name : str
          The name of the target object.
        Returns
        -------
        index : int
          The index of the face in collisoin.
        '''
        pass

    def point(self, name):
        '''
        The 3D point of closest distance on the mesh with the given name.
        Parameters
        ----------
        name : str
          The name of the target object.
        Returns
        -------
        point : (3,) float
          The closest point.
        '''
        pass
```

**Rewrite**

```python
class DistanceData:
    '''
    Container encapsulating details of a distance measurement between two entities.
    '''

    def __init__(self, names, result):
        '''
        Construct a new DistanceData object.
        Parameters
        ----------
        names : list of str
          The identifiers of the two objects in sequence.
        contact : fcl.DistanceResult
          The collision distance computation result from FCL.
        '''
        pass
    @property
    def distance(self):
        '''
        Delivers the calculated straight-line separation between the two entities.
        Returns
        -------
        distance : float
          The Euclidean distance value separating the objects.
        '''
        pass

    def index(self, name):
        '''
        Provides the index of the nearest triangular face on the specified mesh during collision analysis.
        Parameters
        ----------
        name : str
          The identifier of the target mesh object.
        Returns
        -------
        index : int
          The integer face index within the collision dataset.
        '''
        pass

    def point(self, name):
        '''
        Returns the three-dimensional coordinates of the nearest point on the specified mesh.
        Parameters
        ----------
        name : str
          The name of the mesh (one component of the two-object pair).
        Returns
        -------
        point : (3,) float
          The Cartesian (x, y, z) location of minimum distance on the mesh surface.
        '''
        pass
```

_judge: EQUIVALENT — All differences are clarifying rephrasings (e.g., "triangular face" instead of "face", "Cartesian coordinates" instead of "3D point") that do not alter the core requirements, types, or behavior specified in the original docstrings._

---

## 91. RealClassEval/post_cut-off/snippet_109 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class Sentence:
    '''Class to represent a sentence.
    Attributes:
        text (str): The text of the sentence.
        start_index (int): The starting index of the sentence in the original text.
        end_index (int): The ending index of the sentence in the original text.
        token_count (int): The number of tokens in the sentence.
    '''

    def __post_init__(self) -> None:
        '''Validate attributes.'''
        pass

    def __repr__(self) -> str:
        '''Return a string representation of the Sentence.'''
        pass

    def to_dict(self) -> Dict[str, Union[str, int]]:
        '''Return the Chunk as a dictionary.'''
        pass
    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int]]) -> 'Sentence':
        '''Create a Sentence object from a dictionary.'''
        pass
```

**Rewrite**

```python
@dataclass
class Sentence:
    '''Sentence class: text (str), start_index (int) in original text, end_index (int) in original text, token_count (int)
    '''

    def __post_init__(self) -> None:
        '''Validate attributes'''
        pass

    def __repr__(self) -> str:
        '''String representation of Sentence'''
        pass

    def to_dict(self) -> Dict[str, Union[str, int]]:
        '''Chunk as dictionary'''
        pass
    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int]]) -> 'Sentence':
        '''Create Sentence from dictionary'''
        pass
```

_judge: EQUIVALENT — The rewritten specification maintains identical requirements for attributes, methods, and behavior with only minor stylistic changes that do not alter meaning or functionality._

---

## 92. RealClassEval/post_cut-off/snippet_71 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class HookEvent:
    '''Base class for all hook events.
    Attributes:
        agent: The agent instance that triggered this event.
    '''
    @property
    def should_reverse_callbacks(self) -> bool:
        '''Determine if callbacks for this event should be invoked in reverse order.
        Returns:
            False by default. Override to return True for events that should
            invoke callbacks in reverse order (e.g., cleanup/teardown events).
        '''
        pass

    def _can_write(self, name: str) -> bool:
        '''Check if the given property can be written to.
        Args:
            name: The name of the property to check.
        Returns:
            True if the property can be written to, False otherwise.
        '''
        pass

    def __post_init__(self) -> None:
        '''Disallow writes to non-approved properties.'''
        pass

    def __setattr__(self, name: str, value: Any) -> None:
        '''Prevent setting attributes on hook events.
        Raises:
            AttributeError: Always raised to prevent setting attributes on hook events.
        '''
        pass
```

**Rewrite**

```python
@dataclass
class HookEvent:
    '''Base hook event class.
    Attributes:
        agent: triggering agent instance.
    '''
    @property
    def should_reverse_callbacks(self) -> bool:
        '''Return reverse callback order flag.
        Returns:
            False. Override to True for cleanup/teardown events.
        '''
        pass

    def _can_write(self, name: str) -> bool:
        '''Check property writability.
        Args:
            name: property name
        Returns:
            writable flag
        '''
        pass

    def __post_init__(self) -> None:
        '''Disallows writes to non-approved properties.'''
        pass

    def __setattr__(self, name: str, value: Any) -> None:
        '''Prevents attribute setting on hook events.
        Raises:
            AttributeError (always)
        '''
        pass
```

_judge: EQUIVALENT — The rewrite condenses wording without altering any requirements, types, or examples._

---

## 93. RealClassEval/csn/snippet_302 — `llm_terse_01` (terse)

**Original**

```python

class ErrorHandler:
    '''
    Custom error handler providing a response on a particular error.
    '''
    @abstractmethod
    def can_handle(self, e):
        '''
        Indicator if the handler is able to handle the given exception `e`.
        :param e: The exception that shall be determined if can be handled by the handler.
        :return: `True` or `False` depending on whether the handler can/should handle the method.
        '''
        pass
    @abstractmethod
    def handle(self, e):
        '''
        Handle the exception.
        :param e: The handled exception.
        :return: The error response for the exception.
        '''
        pass
```

**Rewrite**

```python

class ErrorHandler:
    '''
    Custom error handler providing responses for specific errors.
    '''
    @abstractmethod
    def can_handle(self, e):
        '''
        Indicates if handler can handle `e`.
        :param e: Exception `e` to check if handler can handle.
        :return: `True` or `False` if handler can/should handle the method.
        '''
        pass
    @abstractmethod
    def handle(self, e):
        '''
        Handles exception, returns error response.
        :param e: Exception `e` to handle.
        :return: Error response for exception.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and minor wording adjustments (e.g., singular to plural) without changing any functional requirements, parameter types, return values, or behavioral expectations._

---

## 94. RealClassEval/post_cut-off/snippet_50 — `llm_lexical_01` (lexical)

**Original**

```python

class FFTConvolution:
    '''
    Initial implementation of fft_convolution task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the FFTConvolution.'''
        pass

    def solve(self, problem):
        '''
        Solve the fft_convolution problem.
        Args:
            problem: Dictionary containing problem data specific to fft_convolution
        Returns:
            The solution in the format expected by the task
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Check if the provided solution is valid.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

**Rewrite**

```python

class FFTConvolution:
    '''
    Preliminary implementation of the fft_convolution task.
    This will be refined by OpenEvolve to increase performance and correctness.
    '''

    def __init__(self):
        '''Set up a new FFTConvolution object.'''
        pass

    def solve(self, problem):
        '''
        Solve the fft_convolution problem.
        Args:
            problem: Dictionary containing data specific to the fft_convolution problem
        Returns:
            Solution in the format required by the task
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Verify the validity of the supplied solution for the problem.
        Args:
            problem: The original problem
            solution: The solution to check
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing (e.g., "preliminary" vs "initial", "refined" vs "evolved", "required" vs "expected") without changing any requirements, types, arguments, return values, or behavior._

---

## 95. RealClassEval/post_cut-off/snippet_288 — `llm_formal_01` (formal)

**Original**

```python
@dataclass
class ParserExtensionConfig:
    '''Parser extension configuration.'''
    @staticmethod
    def encode_base64(text: str) -> str:
        '''Encode a string to base64.
        Args:
            log: Raw string
        Returns:
            Base64 encoded string
        '''
        pass

    def __post_init__(self) -> None:
        '''Post initialization hook for field processing.'''
        pass

    def validate(self) -> None:
        '''Validate configuration.
        Raises:
            ValueError: If configuration is invalid
        '''
        pass

    def to_dict(self) -> Dict:
        '''Convert to dictionary format for API request.
        Returns:
            Dict containing the configuration in API format
        Raises:
            ValueError: If configuration is invalid
        '''
        pass
```

**Rewrite**

```python
@dataclass
class ParserExtensionConfig:
    '''Configuration for parser extensions.'''
    @staticmethod
    def encode_base64(text: str) -> str:
        '''Encodes a raw string to a base64 encoded string.
        Args:
            log: the raw string to be encoded
        Returns:
            a base64 encoded string
        '''
        pass

    def __post_init__(self) -> None:
        '''Executes post-initialization processing of configuration fields.'''
        pass

    def validate(self) -> None:
        '''Validates the configuration against defined requirements.
        Raises:
            ValueError: if the configuration is invalid
        '''
        pass

    def to_dict(self) -> Dict:
        '''Converts the configuration to a dictionary representation for API transmission.
        Returns:
            a dictionary containing the configuration in API format
        Raises:
            ValueError: if the configuration is invalid
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases docstrings descriptively without altering requirements, argument types, return values, or exception conditions._

---

## 96. RealClassEval/post_cut-off/snippet_280 — `llm_terse_01` (terse)

**Original**

```python

class BoundWorkerMethod:
    '''
    Proxy object that binds a `WorkerTaskWrapper` to an instance (self),
    allowing decorated instance methods to work seamlessly with all
    background execution capabilities.
    This enables you to use:
        instance.method()
        instance.method.async_call(...)
        instance.method.run_and_wait(...)
    without losing access to wrapper methods.
    Attributes:
        _wrapper: The original WorkerTaskWrapper
        _instance: The instance to bind as the first argument
    '''

    def __init__(self, wrapper: 'WorkerTaskWrapper', instance: object):
        '''
        Initialize the proxy with the wrapper and the instance.
        Args:
            wrapper: The WorkerTaskWrapper object
            instance: The object instance to bind to the call
        '''
        pass

    def __call__(self, *args, **kwargs):
        '''
        Synchronous execution with the bound instance.
        Equivalent to: wrapper(instance, *args, **kwargs)
        '''
        pass

    def async_call(self, *args, **kwargs) -> str:
        '''
        Asynchronous execution with the bound instance.
        Returns a worker_id.
        '''
        pass

    def submit(self, *args, **kwargs) -> str:
        '''
        Alias for async_call().
        '''
        pass

    def run_and_wait(self, *args, timeout: Optional[float]=None, **kwargs):
        '''
        Executes the task in the background, then waits for and returns the result.
        Raises:
            RuntimeError: if the task is cancelled
            Exception: if the task failed with an error
        '''
        pass

    def set_pool(self, pool: 'WorkerPool'):
        '''
        Sets a specific pool to use for this task.
        '''
        pass

    def shutdown_default_pool(self):
        '''
        Shuts down the default pool used by this function, if created.
        '''
        pass

    def __getattr__(self, name):
        '''
        Fallback to the wrapper’s attributes for completeness.
        This makes sure any missing attributes are forwarded.
        '''
        pass
```

**Rewrite**

```python

class BoundWorkerMethod:
    '''
    Proxy binding WorkerTaskWrapper to instance self. Enables sync, async_call, run_and_wait. Preserves wrapper access. Attributes: _wrapper (WorkerTaskWrapper), _instance
    '''

    def __init__(self, wrapper: 'WorkerTaskWrapper', instance: object):
        '''
        Initialize with wrapper (WorkerTaskWrapper) and instance
        '''
        pass

    def __call__(self, *args, **kwargs):
        '''
        Sync call: wrapper(instance, *args, **kwargs)
        '''
        pass

    def async_call(self, *args, **kwargs) -> str:
        '''
        Async execution: returns worker_id
        '''
        pass

    def submit(self, *args, **kwargs) -> str:
        '''
        Alias for async_call
        '''
        pass

    def run_and_wait(self, *args, timeout: Optional[float]=None, **kwargs):
        '''
        Waits for background task result; raises RuntimeError (cancelled), Exception (failed)
        '''
        pass

    def set_pool(self, pool: 'WorkerPool'):
        '''
        Set pool for task
        '''
        pass

    def shutdown_default_pool(self):
        '''
        Shutdown default pool if created
        '''
        pass

    def __getattr__(self, name):
        '''
        Forward missing wrapper attributes
        '''
        pass
```

_judge: EQUIVALENT — The rewrite condenses the docstrings without changing requirements, argument types, return values, or behavioral specifications._

---

## 97. RealClassEval/post_cut-off/snippet_255 — `llm_terse_01` (terse)

**Original**

```python

class CacheKeyBuilder:
    '''Helper class to build standardized cache keys.'''
    @staticmethod
    def alerts_key(agent_id: Optional[str]=None, time_range: str='24h', level: Optional[int]=None) -> Dict[str, Any]:
        '''Build cache key for alerts.'''
        pass
    @staticmethod
    def agent_health_key(agent_id: str) -> Dict[str, Any]:
        '''Build cache key for agent health.'''
        pass
    @staticmethod
    def vulnerabilities_key(agent_id: Optional[str]=None, severity: Optional[str]=None) -> Dict[str, Any]:
        '''Build cache key for vulnerabilities.'''
        pass
    @staticmethod
    def processes_key(agent_id: str, include_children: bool=True) -> Dict[str, Any]:
        '''Build cache key for processes.'''
        pass
    @staticmethod
    def ports_key(agent_id: str, state: list[str]=None, protocol: list[str]=None) -> Dict[str, Any]:
        '''Build cache key for ports.'''
        pass
```

**Rewrite**

```python

class CacheKeyBuilder:
    '''Standardized cache key builder'''
    @staticmethod
    def alerts_key(agent_id: Optional[str]=None, time_range: str='24h', level: Optional[int]=None) -> Dict[str, Any]:
        '''Alerts cache key'''
        pass
    @staticmethod
    def agent_health_key(agent_id: str) -> Dict[str, Any]:
        '''Agent health cache key'''
        pass
    @staticmethod
    def vulnerabilities_key(agent_id: Optional[str]=None, severity: Optional[str]=None) -> Dict[str, Any]:
        '''Vulnerabilities cache key'''
        pass
    @staticmethod
    def processes_key(agent_id: str, include_children: bool=True) -> Dict[str, Any]:
        '''Processes cache key'''
        pass
    @staticmethod
    def ports_key(agent_id: str, state: list[str]=None, protocol: list[str]=None) -> Dict[str, Any]:
        '''Ports cache key'''
        pass
```

_judge: EQUIVALENT — The docstring wording changes are superficial and do not alter any functional requirements, parameter types, defaults, or return values._

---

## 98. RealClassEval/post_cut-off/snippet_69 — `llm_terse_01` (terse)

**Original**

```python

class CompositeCallbackHandler:
    '''Class-based callback handler that combines multiple callback handlers.
    This handler allows multiple callback handlers to be invoked for the same events,
    enabling different processing or output formats for the same stream data.
    '''

    def __init__(self, *handlers: Callable) -> None:
        '''Initialize handler.'''
        pass

    def __call__(self, **kwargs: Any) -> None:
        '''Invoke all handlers in the chain.'''
        pass
```

**Rewrite**

```python

class CompositeCallbackHandler:
    '''Composite callback handler: multiple handlers per event, varied stream processing formats.
    '''

    def __init__(self, *handlers: Callable) -> None:
        '''Initialize handler.'''
        pass

    def __call__(self, **kwargs: Any) -> None:
        '''Invoke handlers in chain.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings concisely rephrase the original requirements without altering meaning, adding, dropping, or changing any functional specifications._

---

## 99. RealClassEval/post_cut-off/snippet_346 — `llm_terse_01` (terse)

**Original**

```python

class EventDataNormalizer:
    '''事件数据标准化器'''
    @staticmethod
    def normalize_event_data(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        '''标准化事件数据格式'''
        pass
    @staticmethod
    def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
        '''从事件数据中提取用户ID'''
        pass
    @staticmethod
    def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
        '''从事件数据中提取目标信息，返回(target_id, is_group)'''
        pass
```

**Rewrite**

```python

class EventDataNormalizer:
    '''Event Data Normalizer'''
    @staticmethod
    def normalize_event_data(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        '''Normalize event data'''
        pass
    @staticmethod
    def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
        '''Extract user ID'''
        pass
    @staticmethod
    def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
        '''Extract target info (target_id, is_group)'''
        pass
```

_judge: EQUIVALENT — The docstrings describe identical requirements in different languages without altering the meaning of any specification element._

---

## 100. RealClassEval/post_cut-off/snippet_135 — `llm_formal_01` (formal)

**Original**

```python

class GPUManager:
    '''
    A manager class to handle GPU interactions using pynvml.
    Parameters
    ----------
    gpu_indices : Optional[List[int]]
        List of GPU indices to manage. If None, single GPU is assumed.
    '''

    def __init__(self, gpu_indices: Optional[List[int]]=None) -> None:
        '''Initialize the GPUManager.'''
        pass
    @contextmanager
    def manage_resources(self) -> Generator[None, None, None]:
        '''
        Context manager to ensure pynvml is initialized and shut down properly.
        Yields
        ------
        None
        '''
        pass

    def get_memory_usage(self) -> Dict[int, int]:
        '''
        Get the current memory usage for each managed GPU.
        Returns
        -------
        Dict[int, int]
            Dictionary of memory usage in bytes for each GPU.
        '''
        pass
```

**Rewrite**

```python

class GPUManager:
    '''
    A class for GPU interaction management using the pynvml library.
    Parameters
    ----------
    gpu_indices : Optional[List[int]]
        List of GPU indices to manage. If None, single GPU is assumed.
    '''

    def __init__(self, gpu_indices: Optional[List[int]]=None) -> None:
        '''The initialization of the GPUManager instance.'''
        pass
    @contextmanager
    def manage_resources(self) -> Generator[None, None, None]:
        '''
        A context manager that ensures proper initialization and shutdown of the pynvml library.
        Yields
        ------
        None
        '''
        pass

    def get_memory_usage(self) -> Dict[int, int]:
        '''
        Retrieves the current memory usage in bytes for each managed GPU and returns a dictionary mapping GPU indices (integers) to memory usage values in bytes (integers).
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the requirements without changing the meaning, types, or behavior specified in the original._

---

## 101. RealClassEval/csn/snippet_249 — `llm_terse_01` (terse)

**Original**

```python

class Template:
    '''Provide tool to managed templates
    '''

    def __init__(self):
        '''Class instantiation
        '''
        pass

    def render(self, sources, config, out=sys.stdout):
        '''Render the documentation as defined in config Object
        '''
        pass
```

**Rewrite**

```python

class Template:
    '''Template management
    '''

    def __init__(self):
        '''Class instantiation
        '''
        pass

    def render(self, sources, config, out=sys.stdout):
        '''Render config documentation
        '''
        pass
```

_judge: EQUIVALENT — The docstring changes only rephrase the same requirement without altering its meaning or scope._

---

## 102. RealClassEval/post_cut-off/snippet_19 — `llm_formal_01` (formal)

**Original**

```python

class MarkdownCleaner:
    '''
    封装 Markdown 清理逻辑：直接用 MarkdownCleaner.clean_markdown(text) 即可
    '''
    @staticmethod
    def _replace_inline_dollar(m: re.Match) -> str:
        '''
        只要捕获到完整的 "$...$":
          - 如果内部有典型公式字符 => 去掉两侧 $
          - 否则 (纯数字/货币等) => 保留 "$...$"
        '''
        pass
    @staticmethod
    def _replace_table_block(match: re.Match) -> str:
        '''
        当匹配到一个整段表格块时，回调该函数。
        '''
        pass
    @staticmethod
    def clean_markdown(text: str) -> str:
        '''
        主入口方法：依序执行所有正则，移除或替换 Markdown 元素
        '''
        pass
```

**Rewrite**

```python

class MarkdownCleaner:
    '''
    This class provides a static method for cleaning Markdown content. The static method `clean_markdown` serves as a direct interface for Markdown sanitization.
    '''
    @staticmethod
    def _replace_inline_dollar(m: re.Match) -> str:
        '''
        When a complete '$...$' pattern is matched (i.e., a string beginning and ending with a dollar sign):
            - If the substring between the dollar signs contains typical formula characters, the leading and trailing dollar signs are removed.
            - Otherwise, if the substring between the dollar signs consists solely of numerals or currency symbols, the entire '$...$' string is preserved.
        '''
        pass
    @staticmethod
    def _replace_table_block(match: re.Match) -> str:
        '''
        When a complete table block match is detected, the static method `_replace_table_block` is called with a match object representing the block as argument. It returns a string containing the transformed table block.
        '''
        pass
    @staticmethod
    def clean_markdown(text: str) -> str:
        '''
        The input Markdown string is processed sequentially by the static method `clean_markdown` using a series of regular expression substitutions designed to remove or replace Markdown structural elements.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite translates and elaborates the original requirements in English without altering any functional behavior, input/output specifications, or conditions._

---

## 103. RealClassEval/csn/snippet_35 — `llm_formal_01` (formal)

**Original**

```python

class __Timer__:
    '''Computes elapsed time, between tic, tac, and toc.
    Methods
    -------
    tic :
        Resets timer.
    toc :
        Returns and prints time elapsed since last tic().
    tac :
        Returns and prints time elapsed since last
             tic(), tac() or toc() whichever occured last.
    loop_timer :
        Returns and prints the total and average time elapsed for n runs
        of a given function.
    '''

    def tic(self):
        '''
        Save time for future use with `tac()` or `toc()`.
        Returns
        -------
        None
            This function doesn't return a value.
        '''
        pass

    def tac(self, verbose=True, digits=2):
        '''
        Return and print elapsed time since last `tic()`, `tac()`, or
        `toc()`.
        Parameters
        ----------
        verbose : bool, optional(default=True)
            If True, then prints time.
        digits : scalar(int), optional(default=2)
            Number of digits printed for time elapsed.
        Returns
        -------
        elapsed : scalar(float)
            Time elapsed since last `tic()`, `tac()`, or `toc()`.
        '''
        pass

    def toc(self, verbose=True, digits=2):
        '''
        Return and print time elapsed since last `tic()`.
        Parameters
        ----------
        verbose : bool, optional(default=True)
            If True, then prints time.
        digits : scalar(int), optional(default=2)
            Number of digits printed for time elapsed.
        Returns
        -------
        elapsed : scalar(float)
            Time elapsed since last `tic()`.
        '''
        pass

    def loop_timer(self, n, function, args=None, verbose=True, digits=2, best_of=3):
        '''
        Return and print the total and average time elapsed for n runs
        of function.
        Parameters
        ----------
        n : scalar(int)
            Number of runs.
        function : function
            Function to be timed.
        args : list, optional(default=None)
            Arguments of the function.
        verbose : bool, optional(default=True)
            If True, then prints average time.
        digits : scalar(int), optional(default=2)
            Number of digits printed for time elapsed.
        best_of : scalar(int), optional(default=3)
            Average time over best_of runs.
        Returns
        -------
        average_time : scalar(float)
            Average time elapsed for n runs of function.
        average_of_best : scalar(float)
            Average of best_of times for n runs of function.
        '''
        pass
```

**Rewrite**

```python

class __Timer__:
    '''This class computes the elapsed time between the events tic, tac, and toc. It provides methods to reset the timer and to record time intervals. Method tic resets the timer. Method toc returns and prints the time elapsed since the last invocation of tic. Method tac returns and prints the time elapsed since the most recent occurrence of tic, tac, or toc. Method loop_timer returns and prints the total and average time elapsed for n executions of a specified function.
    '''

    def tic(self):
        '''
        The current time is recorded for subsequent use with tac or toc. No value is returned.
        '''
        pass

    def tac(self, verbose=True, digits=2):
        '''
        This method returns and prints the time interval in seconds since the most recent occurrence of tic, tac, or toc. Parameters: verbose (bool, optional, default=True): If true, the elapsed time is printed. digits (int, scalar, optional, default=2): Specifies the number of decimal digits for the printed time. Returns: elapsed (float, scalar): The time interval in seconds between the last trigger event among tic, tac, or toc and the current call.
        '''
        pass

    def toc(self, verbose=True, digits=2):
        '''
        This method returns and prints the time interval in seconds since the last invocation of tic. Parameters: verbose (bool, optional, default=True): If true, the elapsed time is printed. digits (int, scalar, optional, default=2): Specifies the number of decimal digits for the printed time. Returns: elapsed (float, scalar): The time interval in seconds between the last call to tic and the current call.
        '''
        pass

    def loop_timer(self, n, function, args=None, verbose=True, digits=2, best_of=3):
        '''
        This method executes the specified function n times and returns the total and average elapsed time for these executions. Parameters: n (int, scalar): The number of function executions. function (callable): The function to be timed. args (list, optional, default=None): The arguments passed to the function. verbose (bool, optional, default=True): If true, the average time is printed. digits (int, scalar, optional, default=2): Specifies the number of decimal digits for printed time values. best_of (int, scalar, optional, default=3): The number of fastest executions to average for computing average_of_best. Returns: average_time (float, scalar): The arithmetic mean of execution times over n runs. average_of_best (float, scalar): The arithmetic mean of the best_of fastest execution times.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification preserves all behavioral requirements, parameters, return values, and examples using synonymous phrasing without altering any technical details or constraints._

---

## 104. RealClassEval/post_cut-off/snippet_262 — `llm_terse_01` (terse)

**Original**

```python

class STMessages:
    '''A class to handle Streamlit messages.'''

    def success(self, message: str='Operation completed successfully.'):
        '''Display a success message.'''
        pass

    def warning(self, message: str='Holy! the dev forgot to write this warning messsage lol 💀.'):
        '''Display a warning message.'''
        pass

    def error(self, message: str='An error occurred.'):
        '''Display an error message.'''
        pass

    def skull(self, message: str='💀'):
        '''Display a skull message.'''
        pass
```

**Rewrite**

```python

class STMessages:
    '''Streamlit message handler'''

    def success(self, message: str='Operation completed successfully.'):
        '''Success message'''
        pass

    def warning(self, message: str='Holy! the dev forgot to write this warning messsage lol 💀.'):
        '''Warning message'''
        pass

    def error(self, message: str='An error occurred.'):
        '''Error message'''
        pass

    def skull(self, message: str='💀'):
        '''Skull message'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings are concise paraphrases of the originals without altering the meaning of the requirements, argument types, defaults, or intended behavior._

---

## 105. RealClassEval/post_cut-off/snippet_346 — `llm_lexical_01` (lexical)

**Original**

```python

class EventDataNormalizer:
    '''事件数据标准化器'''
    @staticmethod
    def normalize_event_data(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        '''标准化事件数据格式'''
        pass
    @staticmethod
    def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
        '''从事件数据中提取用户ID'''
        pass
    @staticmethod
    def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
        '''从事件数据中提取目标信息，返回(target_id, is_group)'''
        pass
```

**Rewrite**

```python

class EventDataNormalizer:
    '''事件数据标准化工具'''
    @staticmethod
    def normalize_event_data(event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        '''将事件数据格式标准化'''
        pass
    @staticmethod
    def extract_user_id(event_data: Dict[str, Any]) -> Optional[str]:
        '''从事件数据中提取用户标识'''
        pass
    @staticmethod
    def extract_target_info(event_data: Dict[str, Any]) -> tuple[Optional[str], bool]:
        '''从事件数据中获取目标信息，返回(target_id, is_group)'''
        pass
```

_judge: EQUIVALENT — The docstring wording changes (e.g., "标准化器" vs "标准化工具", "ID" vs "标识", "提取" vs "获取") are stylistic variations that do not alter the functional requirements, input/output specifications, or behavior described in the original._

---

## 106. RealClassEval/post_cut-off/snippet_151 — `llm_lexical_01` (lexical)

**Original**

```python

class SimpleAgent:
    '''
    A simple agent that selects actions for the TutorEnv.
    This is a placeholder for an actual Atropos policy.
    '''

    def __init__(self, action_space):
        '''Initialize with the action space of the environment.'''
        pass

    def select_action(self, observation):
        '''
        Select an action based on the current observation.
        Uses simple epsilon-greedy strategy.
        '''
        pass

    def update(self, action, reward):
        '''Update action values based on reward.'''
        pass
```

**Rewrite**

```python

class SimpleAgent:
    '''
    A basic agent designed to choose actions within the TutorEnv environment. This implementation serves as a temporary substitute for the functional Atropos policy.
    '''

    def __init__(self, action_space):
        '''Configure the agent using the action space provided by the environment.'''
        pass

    def select_action(self, observation):
        '''
        Pick an action given the current observation. It relies on a fundamental epsilon-greedy decision-making approach.
        '''
        pass

    def update(self, action, reward):
        '''Modify stored action values in response to the received reward signal.'''
        pass
```

_judge: EQUIVALENT — The docstring changes only use synonymous phrasing (e.g., "simple" vs "basic", "placeholder" vs "temporary substitute") without altering requirements, types, or behavior semantics._

---

## 107. RealClassEval/csn/snippet_41 — `llm_formal_01` (formal)

**Original**

```python

class lazy_property:
    '''Used to load numba first time it is needed.'''

    def __init__(self, fget):
        '''Lazy load a property with `fget`.'''
        pass

    def __get__(self, obj, cls):
        '''Call the function, set the attribute.'''
        pass
```

**Rewrite**

```python

class lazy_property:
    '''numba is loaded upon the first access of the property.'''

    def __init__(self, fget):
        '''The property is lazily loaded using the function `fget`.'''
        pass

    def __get__(self, obj, cls):
        '''The function is called and the attribute is set.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using passive voice and synonyms without changing any functional behavior, parameters, or examples._

---

## 108. RealClassEval/post_cut-off/snippet_321 — `llm_lexical_01` (lexical)

**Original**

```python
@dataclass
class RegistryConfig:
    '''Configuration for a Schema Registry instance.'''

    def to_dict(self) -> Dict[str, Any]:
        '''Convert to dictionary with sensitive data masked.'''
        pass

    def __repr__(self) -> str:
        '''Safe representation without credentials.'''
        pass

    def __str__(self) -> str:
        '''Safe string representation without credentials.'''
        pass
```

**Rewrite**

```python
@dataclass
class RegistryConfig:
    '''The configuration of a Schema Registry instance.'''

    def to_dict(self) -> Dict[str, Any]:
        '''Transforms the object into a dictionary while masking confidential data.'''
        pass

    def __repr__(self) -> str:
        '''Generates a debug-friendly string that omits credential details.'''
        pass

    def __str__(self) -> str:
        '''Produces a user-facing string that excludes secret values.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing (e.g., "sensitive data" vs. "confidential data", "credentials" vs. "secret values") without changing functional requirements or data handling semantics._

---

## 109. RealClassEval/post_cut-off/snippet_359 — `llm_lexical_01` (lexical)

**Original**

```python

class DRFPUtil:
    '''
    A utility class for encoding SMILES as drfp fingerprints.
        '''
    @staticmethod
    def shingling_from_mol(in_mol: Mol, radius: int=3, rings: bool=True, min_radius: int=0, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[List[str], Tuple[List[str], Dict[str, List[Set[int]]]]]:
        '''Creates a molecular shingling from a RDKit molecule (rdkit.Chem.rdchem.Mol).
        Arguments:
            in_mol: A RDKit molecule instance
            radius: The drfp radius (a radius of 3 corresponds to drfp6)
            rings: Whether or not to include rings in the shingling
            min_radius: The minimum radius that is used to extract n-grams
        Returns:
            The molecular shingling.
        '''
        pass
    @staticmethod
    def internal_encode(in_smiles: str, radius: int=3, min_radius: int=0, rings: bool=True, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Creates an drfp array from a reaction SMILES string.
        Arguments:
            in_smiles: A valid reaction SMILES string
            radius: The drfp radius (a radius of 3 corresponds to drfp6)
            min_radius: The minimum radius that is used to extract n-grams
            rings: Whether or not to include rings in the shingling
        Returns:
            A tuple with two arrays, the first containing the drfp hash values, the second the substructure SMILES
        '''
        pass
    @staticmethod
    def hash(shingling: List[str]) -> np.ndarray:
        '''Directly hash all the SMILES in a shingling to a 32-bit integer.
        Arguments:
            shingling: A list of n-grams
        Returns:
            A list of hashed n-grams
        '''
        pass
    @staticmethod
    def fold(hash_values: np.ndarray, length: int=2048) -> Tuple[np.ndarray, np.ndarray]:
        '''Folds the hash values to a binary vector of a given length.
        Arguments:
            hash_value: An array containing the hash values
            length: The length of the folded fingerprint
        Returns:
            A tuple containing the folded fingerprint and the indices of the on bits
        '''
        pass
    @staticmethod
    def encode(X: Union[Iterable, str], n_folded_length: int=2048, min_radius: int=0, radius: int=3, rings: bool=True, mapping: bool=False, atom_index_mapping: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False, show_progress_bar: bool=False) -> Union[List[np.ndarray], Tuple[List[np.ndarray], Dict[int, Set[str]]], Tuple[List[np.ndarray], Dict[int, Set[str]]], List[Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Encodes a list of reaction SMILES using the drfp fingerprint.
        Args:
            X: An iterable (e.g. List) of reaction SMILES or a single reaction SMILES to be encoded
            n_folded_length: The folded length of the fingerprint (the parameter for the modulo hashing)
            min_radius: The minimum radius of a substructure (0 includes single atoms)
            radius: The maximum radius of a substructure
            rings: Whether to include full rings as substructures
            mapping: Return a feature to substructure mapping in addition to the fingerprints
            atom_index_mapping: Return the atom indices of mapped substructures for each reaction
            root_central_atom: Whether to root the central atom of substructures when generating SMILES
            show_progress_bar: Whether to show a progress bar when encoding reactions
        Returns:
            A list of drfp fingerprints or, if mapping is enabled, a tuple containing a list of drfp fingerprints and a mapping dict.
        '''
        pass
```

**Rewrite**

```python

class DRFPUtil:
    '''
    Provides functionality to convert SMILES strings into drfp fingerprint encodings.
        '''
    @staticmethod
    def shingling_from_mol(in_mol: Mol, radius: int=3, rings: bool=True, min_radius: int=0, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[List[str], Tuple[List[str], Dict[str, List[Set[int]]]]]:
        '''Generates a molecular shingling (collection of n-gram substructures) from an RDKit molecule instance.
        Arguments:
            in_mol: An RDKit molecule instance
            radius: The drfp radius (where 3 maps to drfp6)
            rings: Flag for including ring substructures in the shingling
            min_radius: Minimum radius for n-gram extraction
        Returns:
            The resulting molecular shingling set.
        '''
        pass
    @staticmethod
    def internal_encode(in_smiles: str, radius: int=3, min_radius: int=0, rings: bool=True, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Produces a drfp feature array derived from a reaction SMILES string.
        Arguments:
            in_smiles: A valid reaction SMILES string
            radius: The drfp radius (with 3 corresponding to drfp6)
            min_radius: Minimum radius for n-gram extraction
            rings: Flag indicating ring substructure inclusion
        Returns:
            A pair of arrays: first contains drfp hash values, second holds substructure SMILES strings.
        '''
        pass
    @staticmethod
    def hash(shingling: List[str]) -> np.ndarray:
        '''Converts each n-gram string in the shingling to its 32-bit integer hash value.
        Arguments:
            shingling: A list of n-grams
        Returns:
            The list of resulting integer hash values.
        '''
        pass
    @staticmethod
    def fold(hash_values: np.ndarray, length: int=2048) -> Tuple[np.ndarray, np.ndarray]:
        '''Reduces hash values to a fixed-size binary fingerprint vector.
        Arguments:
            hash_value: Array of integer hash values
            length: Target dimensionality for the folded fingerprint
        Returns:
            Tuple containing the folded binary fingerprint and indices of set bits.
        '''
        pass
    @staticmethod
    def encode(X: Union[Iterable, str], n_folded_length: int=2048, min_radius: int=0, radius: int=3, rings: bool=True, mapping: bool=False, atom_index_mapping: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False, show_progress_bar: bool=False) -> Union[List[np.ndarray], Tuple[List[np.ndarray], Dict[int, Set[str]]], Tuple[List[np.ndarray], Dict[int, Set[str]]], List[Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Transforms one or more reaction SMILES strings into drfp fingerprint arrays.
        Args:
            X: Reaction SMILES string or iterable thereof
            n_folded_length: Folded fingerprint length (modulo hashing parameter)
            min_radius: Minimum substructure radius (0 includes atoms)
            radius: Maximum substructure radius
            rings: Flag for including full ring structures
            mapping: Include feature-to-substructure mapping in return
            atom_index_mapping: Include atom indices for mapped substructures
            root_central_atom: Root the central atom during SMILES generation
            show_progress_bar: Display progress during encoding
        Returns:
            List of drfp fingerprints or, with mapping enabled, a tuple of fingerprints and mapping dictionary.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and clarifying explanations without altering any functional requirements, argument semantics, return value meanings, or examples._

---

## 110. RealClassEval/csn/snippet_216 — `llm_terse_01` (terse)

**Original**

```python

class PowerManagementObserver:
    '''
    Base class for PowerManagement observers.
    Do not make assumptions in what thread or event loop these methods are called.
    '''
    @abstractmethod
    def on_power_sources_change(self, power_management):
        '''
        @param power_management: Instance of PowerManagement posted notification
        '''
        pass
    @abstractmethod
    def on_time_remaining_change(self, power_management):
        '''
        @param power_management: Instance of PowerManagement posted notification
        '''
        pass
```

**Rewrite**

```python

class PowerManagementObserver:
    '''
    PowerManagement observer base class. No thread/event loop assumptions.
    '''
    @abstractmethod
    def on_power_sources_change(self, power_management):
        '''
        @param power_management: Posted PowerManagement instance
        '''
        pass
    @abstractmethod
    def on_time_remaining_change(self, power_management):
        '''
        @param power_management: Posted PowerManagement instance
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing (e.g., "Posted PowerManagement instance" instead of "Instance of PowerManagement posted notification") without changing any requirement, type, or behavior._

---

## 111. RealClassEval/csn/snippet_86 — `llm_lexical_01` (lexical)

**Original**

```python

class Cmd2AttributeWrapper:
    '''Wraps a cmd2-specific attribute added to an argparse Namespace.
    This makes it easy to know which attributes in a Namespace are
    arguments from a parser and which were added by cmd2.
    '''

    def __init__(self, attribute: Any) -> None:
        '''Initialize Cmd2AttributeWrapper instances.'''
        pass

    def get(self) -> Any:
        '''Get the value of the attribute.'''
        pass

    def set(self, new_val: Any) -> None:
        '''Set the value of the attribute.'''
        pass
```

**Rewrite**

```python

class Cmd2AttributeWrapper:
    '''Encapsulates a cmd2-exclusive attribute embedded within an argparse Namespace.
    This facilitates distinguishing between parser-supplied arguments and cmd2-appended attributes in the Namespace.
    '''

    def __init__(self, attribute: Any) -> None:
        '''Creates new instances of the Cmd2AttributeWrapper class.'''
        pass

    def get(self) -> Any:
        '''Fetches the current value held by the attribute.'''
        pass

    def set(self, new_val: Any) -> None:
        '''Assigns a new value to the attribute.'''
        pass
```

_judge: EQUIVALENT — The docstrings rephrase the same requirements without changing any behavior, parameters, or examples._

---

## 112. RealClassEval/csn/snippet_142 — `llm_formal_01` (formal)

**Original**

```python
class ProjectTemplate:
    ''' Public data which can be set in yaml files
        Yaml data available are:
            'build_dir' : build_dir,    # Build output path
            'debugger' : debugger,      # Debugger
            'export_dir': '',           # Export directory path
            'includes': [],             # include paths
            'linker_file': None,        # linker script file
            'name': name,               # project name
            'macros': [],               # macros
            'misc': {},                 # misc settings related to tools
            'output_type': output_type, # output type, default - exe
            'sources': [],              # source files/folders
            'target': '',               # target
            'template' : [],            # tool template
            'tools_supported': [],      # Tools which are supported,
    '''
    @staticmethod
    def _get_common_data_template():
        ''' Data for tool specific '''
        pass
    @staticmethod
    def _get_tool_specific_data_template():
        ''' Data for tool specific '''
        pass
    @staticmethod
    def get_project_template(name='Default', output_type='exe', debugger=None, build_dir='build'):
        ''' Project data (+ data) '''
        pass
```

**Rewrite**

```python
class ProjectTemplate:
    ''' The public configuration data for a project, which is defined in YAML files, comprises the following attributes: the YAML key 'build_dir' specifies the directory path for build output; the key 'debugger' specifies the debugger configuration; the key 'export_dir' specifies the export directory path; the key 'includes' specifies a list of include directory paths; the key 'linker_file' specifies a linker script file; the key 'name' specifies the project name; the key 'macros' specifies a list of preprocessor macros; the key 'misc' specifies a dictionary of miscellaneous tool settings; the key 'output_type' specifies the output type with a default value of 'exe'; the key 'sources' specifies a list of source file or directory paths; the key 'target' specifies the build target; the key 'template' specifies a list of tool templates; the key 'tools_supported' specifies a list of supported tools.
    '''
    @staticmethod
    def _get_common_data_template():
        ''' The data specific to a particular build tool is defined in this section. '''
        pass
    @staticmethod
    def _get_tool_specific_data_template():
        ''' The data specific to a particular build tool is defined in this section. '''
        pass
    @staticmethod
    def get_project_template(name='Default', output_type='exe', debugger=None, build_dir='build'):
        ''' The project-level data, including core attributes and supplementary information, is defined in this section. '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases attribute descriptions in more detail without altering the core requirements, types, defaults, or behavior of the class or its methods._

---

## 113. RealClassEval/post_cut-off/snippet_47 — `llm_lexical_01` (lexical)

**Original**

```python

class Convolve2DFullFill:
    '''
    Initial implementation of convolve2d_full_fill task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the Convolve2DFullFill.'''
        pass

    def solve(self, problem):
        '''
        Compute the 2D convolution of arrays a and b using "full" mode and "fill" boundary.
        Uses scipy.signal.fftconvolve for efficiency, which implicitly handles "fill" boundary.
        Args:
            problem: A tuple (a, b) of 2D arrays.
        Returns:
            A 2D array containing the convolution result.
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Check if the provided solution is valid.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

**Rewrite**

```python

class Convolve2DFullFill:
    '''
    Starting version of the convolve2d_full_fill operation. This functionality will be refined by OpenEvolve to enhance efficiency and accuracy.
    '''

    def __init__(self):
        '''Constructs a new Convolve2DFullFill instance.'''
        pass

    def solve(self, problem):
        '''
        Executes the 2D convolution operation on arrays a and b utilizing 'full' mode alongside 'fill' boundary conditions. Employs scipy.signal.fftconvolve for computational speed, as it automatically manages the 'fill' boundary treatment.
        Args:
            problem: A tuple (a, b) of 2D arrays.
        Returns:
            A 2D array containing the convolution result.
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Determines if the supplied solution meets the problem's validation criteria.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing (e.g., "enhance efficiency and accuracy" vs "improve performance and correctness") without altering any technical requirements, arguments, return values, or behavior._

---

## 114. RealClassEval/post_cut-off/snippet_370 — `llm_lexical_01` (lexical)

**Original**

```python

class SimpleRegistryClient:
    '''Simple client for querying MCP registries for server discovery.'''

    def __init__(self, registry_url: Optional[str]=None):
        '''Initialize the registry client.
        Args:
            registry_url (str, optional): URL of the MCP registry.
                If not provided, uses the MCP_REGISTRY_URL environment variable
                or falls back to the default demo registry.
        '''
        pass

    def list_servers(self, limit: int=100, cursor: Optional[str]=None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        '''List all available servers in the registry.
        Args:
            limit (int, optional): Maximum number of entries to return. Defaults to 100.
            cursor (str, optional): Pagination cursor for retrieving next set of results.
        Returns:
            Tuple[List[Dict[str, Any]], Optional[str]]: List of server metadata dictionaries and the next cursor if available.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def search_servers(self, query: str) -> List[Dict[str, Any]]:
        '''Search for servers in the registry.
        Args:
            query (str): Search query string.
        Returns:
            List[Dict[str, Any]]: List of matching server metadata dictionaries.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def get_server_info(self, server_id: str) -> Dict[str, Any]:
        '''Get detailed information about a specific server.
        Args:
            server_id (str): ID of the server.
        Returns:
            Dict[str, Any]: Server metadata dictionary.
        Raises:
            requests.RequestException: If the request fails.
            ValueError: If the server is not found.
        '''
        pass

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        '''Find a server by its name.
        Args:
            name (str): Name of the server to find.
        Returns:
            Optional[Dict[str, Any]]: Server metadata dictionary or None if not found.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def find_server_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        '''Find a server by exact name match or server ID.
        This is a simple, efficient lookup that only makes network requests when necessary:
        1. Server ID (UUID format) - direct API call
        2. Exact name match from server list - single additional API call
        Args:
            reference (str): Server reference (ID or exact name).
        Returns:
            Optional[Dict[str, Any]]: Server metadata dictionary or None if not found.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass
```

**Rewrite**

```python

class SimpleRegistryClient:
    '''Basic tool for inspecting MCP registries to locate server instances.'''

    def __init__(self, registry_url: Optional[str]=None):
        '''Set up the registry client instance.
        Args:
            registry_url (str, optional): URL of the MCP registry.
                If not provided, uses the MCP_REGISTRY_URL environment variable
                or falls back to the default demo registry.
        '''
        pass

    def list_servers(self, limit: int=100, cursor: Optional[str]=None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        '''Retrieve a collection of servers registered in the MCP service directory.
        Args:
            limit (int, optional): Threshold for the number of records to fetch. Defaults to 100.
            cursor (str, optional): Token for fetching subsequent result batches.
        Returns:
            Pair containing a list of dictionaries with server metadata and an optional string cursor for the next page.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def search_servers(self, query: str) -> List[Dict[str, Any]]:
        '''Locate servers within the registry matching the specified criteria.
        Args:
            query (str): search terms to match against server records.
        Returns:
            Collection of dictionaries representing servers that satisfied the search.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def get_server_info(self, server_id: str) -> Dict[str, Any]:
        '''Fetch comprehensive details for a particular server.
        Args:
            server_id (str): ID of the server.
        Returns:
            Complete metadata dictionary for the specified server.
        Raises:
            requests.RequestException: If the request fails.
            ValueError: If the server is not found.
        '''
        pass

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        '''Identify a server using its exact display name.
        Args:
            name (str): Name of the server to find.
        Returns:
            Server metadata dictionary when located, or None if absent.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass

    def find_server_by_reference(self, reference: str) -> Optional[Dict[str, Any]]:
        '''Locate a server via either its unique identifier or precise name match.
        This optimized search performs network operations only when required:
        1. Direct API invocation when the reference is a UUID-formatted server ID
        2. A single supplementary API request to scan registered names when the reference is a name
        Args:
            reference (str): Server reference (ID or exact name).
        Returns:
            Server metadata dictionary or None if not found.
        Raises:
            requests.RequestException: If the request fails.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and clarifies implicit details (e.g., "exact" in name matching) without changing functional requirements, argument types, return values, or exception conditions._

---

## 115. RealClassEval/csn/snippet_208 — `llm_formal_01` (formal)

**Original**

```python

class NullFile:
    '''A file object that is associated to /dev/null.'''

    def __new__(cls):
        '''
        Pass through.
        '''
        pass

    def __init__(self):
        '''no-op'''
        pass
```

**Rewrite**

```python

class NullFile:
    '''An object representing a file that is associated with the null device.'''

    def __new__(cls):
        '''
        The __new__ method returns the result of the base class __new__ implementation without modification.
        '''
        pass

    def __init__(self):
        '''The __init__ method performs no operations.'''
        pass
```

_judge: EQUIVALENT — The docstrings convey identical requirements for the class behavior with only rephrased wording that preserves the original meaning._

---

## 116. RealClassEval/post_cut-off/snippet_55 — `llm_lexical_01` (lexical)

**Original**

```python

class EigenvectorsComplex:
    '''
    Initial implementation of eigenvectors_complex task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the EigenvectorsComplex.'''
        pass

    def solve(self, problem):
        '''
        Solve the eigenvectors_complex problem.
        Args:
            problem: Dictionary containing problem data specific to eigenvectors_complex
        Returns:
            The solution in the format expected by the task
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Check if the provided solution is valid.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

**Rewrite**

```python

class EigenvectorsComplex:
    '''
    Preliminary version of the eigenvectors_complex task.
    Future iterations via OpenEvolve will enhance performance and accuracy.
    '''

    def __init__(self):
        '''Initialize the EigenvectorsComplex class instance.'''
        pass

    def solve(self, problem):
        '''
        Resolve the eigenvectors_complex problem.
        Args:
            problem: A dictionary containing problem data specific to eigenvectors_complex
        Returns:
            The solution adhering to the task's required format
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Confirm whether the supplied solution meets validity criteria.
        Args:
            problem: The original problem instance
            solution: The candidate answer being evaluated
        Returns:
            True when correct, False for any invalid case
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous wording and slightly more specific phrasing but preserves all core requirements, parameter types, return values, and behavioral expectations without adding, dropping, or altering any constraints._

---

## 117. RealClassEval/csn/snippet_273 — `llm_lexical_01` (lexical)

**Original**

```python
class BasePagination:
    '''
    The base class each Pagination class should implement.
        '''

    def paginate_query(self, query, request):
        '''
        :param query: SQLAlchemy ``query``.
        :param request: The request from the view
        :return: The paginated date based on the provided query and request.
        '''
        pass

    def get_paginated_response(self, data):
        '''
        :param data: The paginated data.
        :return: A response containing the paginated data.
        '''
        pass
```

**Rewrite**

```python
class BasePagination:
    '''
    This class serves as the essential base for any Pagination implementation.
        '''

    def paginate_query(self, query, request):
        '''
        :param query: A SQLAlchemy ``query`` instance.
        :param request: The request originating from the view
        :return: The paginated date derived from the supplied query and request.
        '''
        pass

    def get_paginated_response(self, data):
        '''
        :param data: The paginated data resulting from the pagination process.
        :return: A response containing the paginated data.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and minor rewording without altering technical requirements, types, or semantics._

---

## 118. RealClassEval/csn/snippet_180 — `llm_lexical_01` (lexical)

**Original**

```python

class Immutable:
    '''Immutable.'''

    def __init__(self, **kwargs: Any) -> None:
        '''Initialize.'''
        pass

    def __setattr__(self, name: str, value: Any) -> None:
        '''Prevent mutability.'''
        pass
```

**Rewrite**

```python

class Immutable:
    '''Not modifiable after definition.'''

    def __init__(self, **kwargs: Any) -> None:
        '''Establish the object's initial state.'''
        pass

    def __setattr__(self, name: str, value: Any) -> None:
        '''Prevent any changes to attributes.'''
        pass
```

_judge: EQUIVALENT — The docstring wording changes but preserves the exact same behavioral requirements and meaning._

---

## 119. RealClassEval/csn/snippet_252 — `llm_terse_01` (terse)

**Original**

```python
class RGB888Format:
    '''RGB888Format'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Set a given pixel to a color.'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Get the color of a given pixel'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''completely fill/clear the buffer with a color'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''Draw a rectangle at the given location, size and color. The ``fill_rect`` method draws
        both the outline and interior.'''
        pass
```

**Rewrite**

```python
class RGB888Format:
    '''RGB888 pixel format'''
    @staticmethod
    def set_pixel(framebuf, x, y, color):
        '''Set pixel (x,y) color'''
        pass
    @staticmethod
    def get_pixel(framebuf, x, y):
        '''Get pixel (x,y) color'''
        pass
    @staticmethod
    def fill(framebuf, color):
        '''Fill buffer with color'''
        pass
    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        '''Fill rectangle (x,y,width,height) color'''
        pass
```

_judge: EQUIVALENT — All docstring changes are purely syntactic or terminological refinements without altering any functional requirements, argument meanings, or behaviors._

---

## 120. RealClassEval/post_cut-off/snippet_153 — `llm_terse_01` (terse)

**Original**

```python

class ConditionalTracker:
    '''Utility for tracking conditional contexts in Makefiles.'''

    def __init__(self) -> None:
        '''Initialize the conditional tracker.'''
        pass

    def process_line(self, line: str, line_index: int) -> tuple:
        '''Process a line and return the conditional context the line is IN.
        Args:
            line: The line to process
            line_index: Index of the line (for debugging)
        Returns:
            Tuple representing the conditional context the line is IN
        '''
        pass

    def reset(self) -> None:
        '''Reset the tracker state.'''
        pass
    @staticmethod
    def are_mutually_exclusive(context1: tuple, context2: tuple) -> bool:
        '''Check if two conditional contexts are mutually exclusive.
        Two contexts are mutually exclusive if they differ at any conditional level,
        which means they're in different branches of some conditional block.
        Args:
            context1: First conditional context
            context2: Second conditional context
        Returns:
            True if contexts are mutually exclusive
        '''
        pass
```

**Rewrite**

```python

class ConditionalTracker:
    '''Makefile conditional context tracker'''

    def __init__(self) -> None:
        '''Initialize conditional tracker'''
        pass

    def process_line(self, line: str, line_index: int) -> tuple:
        '''Return conditional context of line
        Args:
        line: Makefile line
        line_index: Line index
        Returns:
        Tuple of line conditional context
        '''
        pass

    def reset(self) -> None:
        '''Reset tracker state'''
        pass
    @staticmethod
    def are_mutually_exclusive(context1: tuple, context2: tuple) -> bool:
        '''Check mutual exclusivity: differ at any conditional level
        Args:
        context1: First context
        context2: Second context
        Returns:
        True if mutually exclusive
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases docstrings with equivalent meaning, preserving all requirements, argument/return types, and behavior without adding, dropping, or altering any specification._

---

## 121. RealClassEval/post_cut-off/snippet_201 — `llm_formal_01` (formal)

**Original**

```python
@dataclass
class OverridableConfig:
    '''A class that provides an interface to switch between its field values depending on an override key.'''

    def __post_init__(self) -> None:
        '''Initialize the override key to 'default'.'''
        pass

    def set_override(self, key: str, reset_to_defaults: bool=True) -> None:
        '''Set the overridden values for the config based on the override registry.
        Args:
            key: The key to use for the override.
            reset_to_defaults: If True, reset the values to their defaults if no override is found. This is useful for
                when you switch from different non-default overrides to other non-default overrides.
        '''
        pass
```

**Rewrite**

```python
@dataclass
class OverridableConfig:
    '''A configuration class enabling dynamic switching of instance field values based on an override key.'''

    def __post_init__(self) -> None:
        '''The override key is initialized to the string 'default'.'''
        pass

    def set_override(self, key: str, reset_to_defaults: bool=True) -> None:
        '''The overridden field values of the configuration instance are updated according to the registry entry associated with the specified key. If no override entry exists for the provided key and the reset_to_defaults parameter is true, the configuration fields are reverted to their default values.
        Args:
            key: A string identifier referencing an entry in the override registry.
            reset_to_defaults: A boolean indicating whether to apply default field values when the registry lacks an entry for the key. This parameter enables transitions between distinct non-default override configurations.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses more precise terminology (e.g., "registry entry", "configuration instance") but preserves all functional requirements, conditions, and behaviors described in the original docstrings without adding, dropping, or altering any specification details._

---

## 122. RealClassEval/csn/snippet_186 — `llm_formal_01` (formal)

**Original**

```python
class TnsFilter:
    '''
    Target Namespace filter.
    @ivar tns: A list of target namespaces.
    @type tns: [str,...]
    '''

    def __init__(self, *tns):
        '''
        @param tns: A list of target namespaces.
        @type tns: [str,...]
        '''
        pass

    def add(self, *tns):
        '''
        Add I{targetNamesapces} to be added.
        @param tns: A list of target namespaces.
        @type tns: [str,...]
        '''
        pass

    def match(self, root, ns):
        '''
        Match by I{targetNamespace} excluding those that
        are equal to the specified namespace to prevent
        adding an import to itself.
        @param root: A schema root.
        @type root: L{Element}
        '''
        pass
```

**Rewrite**

```python
class TnsFilter:
    '''
    This class implements a target namespace filter.
    '''

    def __init__(self, *tns):
        '''
        The attribute 'tns' is a list of target namespace strings.
        '''
        pass

    def add(self, *tns):
        '''
        The parameter 'tns' is a list of target namespace strings. The method adds the target namespaces provided in the 'tns' argument.
        '''
        pass

    def match(self, root, ns):
        '''
        The parameter 'root' is a schema root of type L{Element}. The method matches the target namespace of the provided schema root against the filter, excluding the case where the target namespace equals a specified namespace to prevent adding an import to itself.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements without changing any technical specifications, types, or behavioral constraints._

---

## 123. RealClassEval/post_cut-off/snippet_309 — `llm_terse_01` (terse)

**Original**

```python

class LocalFileBlobStore:
    '''File-based blob storage implementation.'''

    def __init__(self, root: str | None=None, janitor_after_h: int=24):
        '''
        Initialize the local file blob store.
        Args:
            root: Root directory for blob storage (defaults to env BLOB_STORE_PATH or CWD/blobs).            janitor_after_h: Number of hours after which blobs are eligible for cleanup
        '''
        pass

    def _path(self, blob_id: str) -> str:
        '''Get the file path for a blob's binary data.'''
        pass

    def _meta_path(self, blob_id: str) -> str:
        '''Get the file path for a blob's metadata.'''
        pass

    def save(self, data: bytes, meta: dict[str, Any]) -> str:
        '''
        Save binary data with metadata.
        Args:
            data: Binary data to store
            meta: Metadata dictionary
        Returns:
            Unique blob ID for the stored data
        '''
        pass

    def load(self, blob_id: str) -> bytes:
        '''
        Load binary data by blob ID.
        Args:
            blob_id: The blob ID to load
        Returns:
            Binary data
        Raises:
            FileNotFoundError: If the blob doesn't exist
        '''
        pass

    def info(self, blob_id: str) -> dict[str, Any]:
        '''
        Get metadata for a blob.
        Args:
            blob_id: The blob ID
        Returns:
            Metadata dictionary
        Raises:
            FileNotFoundError: If the blob doesn't exist
        '''
        pass

    def delete(self, blob_id: str) -> None:
        '''
        Delete a blob and its metadata.
        Args:
            blob_id: The blob ID to delete
        '''
        pass

    def purge_old(self) -> None:
        '''Remove blobs older than the janitor threshold.'''
        pass
```

**Rewrite**

```python

class LocalFileBlobStore:
    '''Local file blob store'''

    def __init__(self, root: str | None=None, janitor_after_h: int=24):
        '''
        Initialize file blob store
        Args:
            root: Root directory (defaults to env BLOB_STORE_PATH or CWD/blobs)
            janitor_after_h: Cleanup age (h)
        '''
        pass

    def _path(self, blob_id: str) -> str:
        '''Blob binary path'''
        pass

    def _meta_path(self, blob_id: str) -> str:
        '''Blob metadata path'''
        pass

    def save(self, data: bytes, meta: dict[str, Any]) -> str:
        '''
        Store binary data with metadata
        Args:
            data: Binary data
            meta: Metadata dict
        Returns:
            Unique blob ID
        '''
        pass

    def load(self, blob_id: str) -> bytes:
        '''
        Load binary data by ID
        Args:
            blob_id: Blob ID
        Returns:
            Binary data
        Raises:
            FileNotFoundError if missing
        '''
        pass

    def info(self, blob_id: str) -> dict[str, Any]:
        '''
        Get blob metadata
        Args:
            blob_id: Blob ID
        Returns:
            Metadata dict
        Raises:
            FileNotFoundError if missing
        '''
        pass

    def delete(self, blob_id: str) -> None:
        '''
        Delete blob by ID
        Args:
            blob_id: Blob ID
        '''
        pass

    def purge_old(self) -> None:
        '''Remove expired blobs'''
        pass
```

_judge: EQUIVALENT — The rewrite preserves all behavioral requirements through synonymous phrasing without altering conditions, types, or semantics._

---

## 124. RealClassEval/post_cut-off/snippet_46 — `llm_lexical_01` (lexical)

**Original**

```python

class AffineTransform2D:
    '''
    Initial implementation of affine_transform_2d task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the AffineTransform2D.'''
        pass

    def solve(self, problem):
        '''
        Solve the affine_transform_2d problem.
        Args:
            problem: Dictionary containing problem data specific to affine_transform_2d
        Returns:
            The solution in the format expected by the task
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Check if the provided solution is valid.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

**Rewrite**

```python

class AffineTransform2D:
    '''
    First version of the affine_transform_2d task system. Designed for iterative enhancement by OpenEvolve to achieve better performance and accuracy.
    '''

    def __init__(self):
        '''Set up the AffineTransform2D instance.'''
        pass

    def solve(self, problem):
        '''
        Address an affine_transform_2d computational problem.
        Args:
            problem: Dictionary containing problem data specific to affine_transform_2d
        Returns:
            The solution in the format expected by the task
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Verify whether a given solution meets the validity criteria.
        Args:
            problem: The original problem
            solution: The proposed solution
        Returns:
            True if the solution is valid, False otherwise
        '''
        pass
```

_judge: EQUIVALENT — The docstrings use synonymous phrasing (e.g., "correctness" vs "accuracy", "solve" vs "address") without changing any functional requirements, argument types, return values, or behavioral expectations._

---

## 125. RealClassEval/csn/snippet_104 — `llm_terse_01` (terse)

**Original**

```python
class BufferSegment:
    '''Represents a segment within a ``BufferWithSegments``.
    This type is essentially a reference to N bytes within a
    ``BufferWithSegments``.
    The object conforms to the buffer protocol.
    '''
    @property
    def offset(self):
        '''The byte offset of this segment within its parent buffer.'''
        pass

    def __len__(self):
        '''Obtain the length of the segment, in bytes.'''
        pass

    def tobytes(self):
        '''Obtain bytes copy of this segment.'''
        pass
```

**Rewrite**

```python
class BufferSegment:
    '''BufferWithSegments segment, byte reference, buffer protocol compliant
    '''
    @property
    def offset(self):
        '''Byte offset within parent buffer'''
        pass

    def __len__(self):
        '''Segment length in bytes'''
        pass

    def tobytes(self):
        '''Bytes copy of segment'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings are concise paraphrases of the original without changing any requirements, types, or behaviors._
