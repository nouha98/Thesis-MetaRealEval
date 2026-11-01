# Paraphrase corpus review sheet (Gate C)

- corpus version: `v1`
- generator: `soofi-s-isar-preview` · judge: `soofi-s-isar-preview`
- sha256: `ca5e4e3149cad6ae46ddcbd96ed23c56798751895be08b1f6518d5582a065d33`
- sample: 72 variants

For each item, mark **equivalent** or **not equivalent**: does the rewrite demand exactly the same function as the original? Wording, tone and the order of requirements are not differences in meaning.

| # | verdict (fill in) | note |
|---|---|---|
| 1 | not equivalent | acquire_write: ValueError now raised when the lock is unavailable with timeout<=0 (original: only on the upgrade-deadlock condition) |
| 2 | equivalent |  |
| 3 | not equivalent | drops every argument and return description in 4 methods (in_mol, radius, rings, min_radius, X, mapping, ...; fold's tuple return) |
| 4 | equivalent |  |
| 5 | equivalent |  |
| 6 | equivalent (minor) | _instantiated_load: adds 'empty dict' (original: no values to load) |
| 7 | equivalent (minor) | closest point described as a tuple of three floats (original: (3,) float array) |
| 8 | equivalent |  |
| 9 | equivalent |  |
| 10 | equivalent |  |
| 11 | equivalent |  |
| 12 | equivalent (minor) | write content(): content narrowed to a string |
| 13 | equivalent |  |
| 14 | equivalent |  |
| 15 | equivalent |  |
| 16 | equivalent |  |
| 17 | equivalent |  |
| 18 | equivalent |  |
| 19 | equivalent |  |
| 20 | not equivalent | class docstring drops the attribute k (:ivar k / :vartype k: int) |
| 21 | equivalent |  |
| 22 | equivalent |  |
| 23 | equivalent |  |
| 24 | equivalent |  |
| 25 | equivalent (minor) | drops :type annotations; formula spelled out in words |
| 26 | equivalent (minor) | _instantiated_load 'provides none' is ambiguous (none = no args, not None) |
| 27 | equivalent |  |
| 28 | equivalent |  |
| 29 | equivalent |  |
| 30 | not equivalent | acquire_write: ValueError if another write lock or read locks exist (original: those block; ValueError only on upgrade deadlock); 'wait at most timeout seconds' lost |
| 31 | equivalent (minor) | file paths described as 'absolute' |
| 32 | equivalent |  |
| 33 | equivalent |  |
| 34 | equivalent |  |
| 35 | equivalent |  |
| 36 | equivalent |  |
| 37 | equivalent |  |
| 38 | equivalent |  |
| 39 | equivalent (minor) | drops the Pollard-Rho-Brent implementation reference |
| 40 | equivalent |  |
| 41 | equivalent |  |
| 42 | not equivalent | drops all parameter/return specs: names (list of str), contact (fcl.DistanceResult), name (str), index (int), distance (float), point ((3,) float) |
| 43 | equivalent |  |
| 44 | equivalent |  |
| 45 | equivalent |  |
| 46 | equivalent |  |
| 47 | equivalent |  |
| 48 | equivalent |  |
| 49 | equivalent |  |
| 50 | equivalent |  |
| 51 | equivalent |  |
| 52 | not equivalent | class docstring adds a condition: upgrade allowed only 'provided no other locks exist' |
| 53 | equivalent |  |
| 54 | equivalent |  |
| 55 | equivalent |  |
| 56 | equivalent |  |
| 57 | equivalent |  |
| 58 | equivalent |  |
| 59 | equivalent |  |
| 60 | equivalent |  |
| 61 | not equivalent | method names changed (Save/Load/Get/Delete; info() written as Get) and info() drops FileNotFoundError |
| 62 | equivalent (minor) | model_string 'optional if require_llm_engine' (original: optional, only used if require_llm_engine) |
| 63 | equivalent |  |
| 64 | equivalent |  |
| 65 | equivalent |  |
| 66 | equivalent |  |
| 67 | equivalent (minor) | write content() collapsed to 'clipboard text'; Dict return type dropped |
| 68 | equivalent |  |
| 69 | equivalent |  |
| 70 | equivalent |  |
| 71 | not equivalent | __init__ docstring drops all three parameters (parent, children, index) |
| 72 | equivalent |  |

---

## 1. RealClassEval/csn/snippet_62 — `llm_lexical_01` (lexical)

**Original**

```python

class ReadWriteLock:
    '''Read-Write lock class. A read-write lock differs from a standard
    threading.RLock() by allowing multiple threads to simultaneously hold a
    read lock, while allowing only a single thread to hold a write lock at the
    same point of time.
    When a read lock is requested while a write lock is held, the reader
    is blocked; when a write lock is requested while another write lock is
    held or there are read locks, the writer is blocked.
    Writers are always preferred by this implementation: if there are blocked
    threads waiting for a write lock, current readers may request more read
    locks (which they eventually should free, as they starve the waiting
    writers otherwise), but a new thread requesting a read lock will not
    be granted one, and block. This might mean starvation for readers if
    two writer threads interweave their calls to acquire_write() without
    leaving a window only for readers.
    In case a current reader requests a write lock, this can and will be
    satisfied without giving up the read locks first, but, only one thread
    may perform this kind of lock upgrade, as a deadlock would otherwise
    occur. After the write lock has been granted, the thread will hold a
    full write lock, and not be downgraded after the upgrading call to
    acquire_write() has been match by a corresponding release().
    '''

    def __init__(self):
        '''Initialize this read-write lock.'''
        pass

    def acquire_read(self, *, timeout=None):
        '''Acquire a read lock for the current thread, waiting at most
        timeout seconds or doing a non-blocking check in case timeout is <= 0.
        In case timeout is None, the call to acquire_read blocks until the
        lock request can be serviced.
        In case the timeout expires before the lock could be serviced, a
        RuntimeError is thrown.'''
        pass

    def acquire_write(self, *, timeout=None):
        '''Acquire a write lock for the current thread, waiting at most
        timeout seconds or doing a non-blocking check in case timeout is <= 0.
        In case the write lock cannot be serviced due to the deadlock
        condition mentioned above, a ValueError is raised.
        In case timeout is None, the call to acquire_write blocks until the
        lock request can be serviced.
        In case the timeout expires before the lock could be serviced, a
        RuntimeError is thrown.'''
        pass

    def release(self):
        '''Release the currently held lock.
        In case the current thread holds no lock, a ValueError is thrown.'''
        pass
```

**Rewrite**

```python

class ReadWriteLock:
    '''Read-Write lock implementation. This lock type permits multiple threads to hold a read lock concurrently while restricting write lock ownership to exactly one thread at any moment.
    When readers attempt to acquire a lock while a write lock is active, they are blocked; similarly, writers trying to acquire a lock are blocked if either another write lock exists or any read locks are held.
    This implementation prioritizes writers: if threads are waiting for a write lock, existing readers may continue acquiring read locks (which they must release to avoid starving pending writers), but new read lock requests from unblocked threads will be denied and cause blocking. Consequently, reader starvation can occur if two writer threads rapidly interleave write lock requests without creating a sufficient window for readers.
    If a thread currently holding read locks requests a write lock, the upgrade is granted without releasing the read locks first; however, only one thread may perform such an upgrade at a time to prevent deadlock. After upgrade, the thread holds a full write lock until explicitly released via the corresponding unlock call, and the lock remains in write mode rather than reverting to read mode.
    '''

    def __init__(self):
        '''Creates a new instance of the read-write lock.'''
        pass

    def acquire_read(self, *, timeout=None):
        '''Acquires a read lock for the current thread. With a positive `timeout`, the method waits up to that many seconds; if `timeout` is zero or negative, it performs a non-blocking check. Omitting `timeout` (or setting it to None) causes indefinite blocking until the lock is acquired. If the lock is not obtained within the specified timeout duration, a RuntimeError is raised.'''
        pass

    def acquire_write(self, *, timeout=None):
        '''Acquires a write lock for the current thread. If `timeout` is positive, the method waits up to `timeout` seconds for the lock to become available; a zero or negative `timeout` triggers an immediate non-blocking attempt. When the lock is unavailable and `timeout` is zero or negative, a ValueError is raised due to the deadlock condition described in the class documentation. Omitting `timeout` (or setting it to None) results in indefinite blocking until the lock is acquired. If the lock is not acquired within the given positive timeout period, a RuntimeError is raised.'''
        pass

    def release(self):
        '''Releases the lock currently owned by the calling thread. If the thread does not hold the lock at the time of invocation, a ValueError is raised.'''
        pass
```

_judge: EQUIVALENT — The rewritten specification describes identical requirements for lock behavior, upgrade semantics, and error conditions using synonymous wording without altering any functional constraints or interface details._

---

## 2. RealClassEval/csn/snippet_54 — `llm_lexical_01` (lexical)

**Original**

```python
class Enum:
    '''Map values to specific strings.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the mapping.'''
        pass

    def __call__(self, val):
        '''Map an integer to the string representation.'''
        pass
```

**Rewrite**

```python
class Enum:
    '''Assign particular string representations to each integer value.'''

    def __init__(self, *args, **kwargs):
        '''Configure the value-to-string associations.'''
        pass

    def __call__(self, val):
        '''Convert an integer value to its string representation.'''
        pass
```

_judge: EQUIVALENT — The docstrings rephrase the same core requirements (mapping integers to strings) without changing scope, constraints, or behavior._

---

## 3. RealClassEval/post_cut-off/snippet_359 — `llm_lexical_01` (lexical)

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
    A class providing tools to transform SMILES chemical strings into DRFP fingerprint encodings.
        '''
    @staticmethod
    def shingling_from_mol(in_mol: Mol, radius: int=3, rings: bool=True, min_radius: int=0, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[List[str], Tuple[List[str], Dict[str, List[Set[int]]]]]:
        '''Generates a molecular shingling (a list of string-based substructure patterns) from an RDKit molecule object.
        '''
        pass
    @staticmethod
    def internal_encode(in_smiles: str, radius: int=3, min_radius: int=0, rings: bool=True, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Calculates a DRFP representation for a reaction SMILES input, producing arrays of hash values and associated substructure SMILES strings.
        '''
        pass
    @staticmethod
    def hash(shingling: List[str]) -> np.ndarray:
        '''Converts each SMILES n-gram in the provided shingling list into a 32-bit integer hash value.
        '''
        pass
    @staticmethod
    def fold(hash_values: np.ndarray, length: int=2048) -> Tuple[np.ndarray, np.ndarray]:
        '''Transforms an array of hash values into a fixed-dimension binary fingerprint vector.
        '''
        pass
    @staticmethod
    def encode(X: Union[Iterable, str], n_folded_length: int=2048, min_radius: int=0, radius: int=3, rings: bool=True, mapping: bool=False, atom_index_mapping: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False, show_progress_bar: bool=False) -> Union[List[np.ndarray], Tuple[List[np.ndarray], Dict[int, Set[str]]], Tuple[List[np.ndarray], Dict[int, Set[str]]], List[Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Computes DRFP fingerprint encodings for chemical reaction SMILES inputs, handling both single strings and iterable collections.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use more descriptive language but preserve all requirements, parameter types, return value semantics, and behavioral specifications without adding, removing, or altering any functional constraints._

---

## 4. RealClassEval/post_cut-off/snippet_293 — `llm_formal_01` (formal)

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
    This class implements a thin wrapper for cosine similarity-based nearest neighbor retrieval using the sklearn NearestNeighbors class.
    :ivar model: A fitted NearestNeighbors instance from scikit-learn.
    :vartype model: NearestNeighbors
    :ivar k: The default number of neighbors to retrieve during search operations.
    :vartype k: int
    '''

    def __init__(self, items, k=3):
        '''
        The method initializes the KNN index by processing provided item-embedding pairs and establishing a default neighbor count.
        :param items: An iterable of two-element tuples, each containing an item identifier and an embedding vector as a sequence of floating-point numbers.
        :type items: Iterable[Tuple[Any, Sequence[float]]]
        :param k: An integer specifying the default number of neighbors to retrieve when not overridden in the neighbors method.
        :type k: int
        '''
        pass

    def neighbors(self, target_emb, k=None):
        '''
        The method retrieves k nearest neighbors to the query embedding using cosine distance metric.
        :param target_emb: An embedding vector represented as a sequence of floating-point numbers for the query.
        :type target_emb: Sequence[float]
        :param k: An integer specifying the number of neighbors to retrieve; if omitted, defaults to the instance attribute k.
        :type k: int
        :return: A list of tuples, each containing an item identifier and the corresponding cosine distance from the query.
        :rtype: List[Tuple[Any, float]]
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses more verbose descriptive language but maintains identical requirements for the class structure, parameter types, default behavior, and return format without altering any technical meaning or constraints._

---

## 5. RealClassEval/csn/snippet_129 — `llm_formal_01` (formal)

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
    '''This class represents a node in a Fenwick tree.'''

    def __init__(self, parent, children, index=None):
        '''This class represents a node in a Fenwick tree. Each node has exactly one parent and multiple children.
        The parameter parent is a FenwickNode instance that is the parent of the node.
        The parameter children is a list of FenwickNode instances that are children of the node.
        The parameter index is an integer representing the node label.
        '''
        pass

    def get_ancestors(self):
        '''The method returns a list of FenwickNode instances representing the ancestors of the node.
        The ancestors are ordered from the earliest ancestor.
        The return value consists of the node's ancestors ordered from the most recent ancestor.
        The return type is list(FenwickNode).
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases requirements with more explicit wording but preserves all core specifications, including the ambiguous ancestor ordering and parameter constraints._

---

## 6. RealClassEval/csn/snippet_3 — `llm_terse_01` (terse)

**Original**

```python

class Serializable:
    '''This is the superclass of all serializable objects.'''

    def save(self, out_file):
        '''Save the model to the given file stream.'''
        pass
    @classmethod
    def load(cls, in_file, instantiate=True):
        '''This is meant to be overridden by subclasses and called with super.
        We return constructor argument values when not being instantiated. Since there are no
        constructor arguments for the Serializable class we just return an empty dictionary.
        '''
        pass
    @classmethod
    def _instantiated_load(cls, in_file, **kwargs):
        '''This is meant to be overridden by subclasses and called with super.
        We return constructor argument values (we have no values to load in this abstract class).
        '''
        pass
```

**Rewrite**

```python

class Serializable:
    '''Serializable superclass'''

    def save(self, out_file):
        '''Save model to file stream'''
        pass
    @classmethod
    def load(cls, in_file, instantiate=True):
        '''Subclass override; call with super. Return constructor args (not instantiated): empty dict
        '''
        pass
    @classmethod
    def _instantiated_load(cls, in_file, **kwargs):
        '''Subclass override; call with super. Return constructor args: empty dict
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings preserve all technical requirements and behaviors through condensed phrasing without altering specifications, types, or examples._

---

## 7. RealClassEval/csn/snippet_28 — `llm_formal_01` (formal)

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
    This class encapsulates information about a distance query.
    '''

    def __init__(self, names, result):
        '''
        The method initializes a DistanceData instance.
        Parameters
        ----------
        names : list of str
          A list containing the names of the two objects in query order.
        contact : fcl.DistanceResult
          An instance of fcl.DistanceResult representing the distance query result.
        '''
        pass
    @property
    def distance(self):
        '''
        The method returns the Euclidean distance between the two objects.
        Returns
        -------
        distance : float
          A floating-point value equal to the Euclidean distance between the two objects.
        '''
        pass

    def index(self, name):
        '''
        The method returns the index of the closest face on the mesh with the given name.
        Parameters
        ----------
        name : str
          A string identifying the target mesh object.
        Returns
        -------
        index : int
          An integer representing the index of the closest face involved in a collision on the target mesh.
        '''
        pass

    def point(self, name):
        '''
        The method returns the three-dimensional point on the mesh with the given name that is closest to the other object in the distance query.
        Parameters
        ----------
        name : str
          A string identifying the target mesh object.
        Returns
        -------
        point : (3,) float
          A tuple of three floating-point numbers representing the 3D coordinates of the closest point.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses more descriptive phrasing but preserves all original requirements, parameter meanings, return value types, and behaviors without adding, dropping, or altering any specifications._

---

## 8. RealClassEval/post_cut-off/snippet_4 — `llm_formal_01` (formal)

**Original**

```python

class MemoryManager:
    '''Simple memory manager that leverages PyTorch's built-in memory optimizations.'''

    def __init__(self):
        '''Initialize the memory manager.'''
        pass

    def get_memory_info(self) -> Dict[str, Any]:
        '''Get current memory usage information.'''
        pass

    def cleanup_memory(self, force: bool=False) -> None:
        '''Free up memory by garbage collection and emptying CUDA cache.'''
        pass

    def get_optimal_training_config(self) -> Dict[str, Any]:
        '''Get recommended configurations for model training based on hardware capabilities.'''
        pass

    def optimize_model_for_training(self, model):
        '''Apply PyTorch's built-in memory optimizations for training.'''
        pass

    def optimize_training_args(self, training_args):
        '''Configure training arguments for efficient memory usage.'''
        pass
```

**Rewrite**

```python

class MemoryManager:
    '''A memory management system that employs built-in memory optimization mechanisms from the PyTorch framework.'''

    def __init__(self):
        '''The memory manager instance is initialized.'''
        pass

    def get_memory_info(self) -> Dict[str, Any]:
        '''Current memory usage information is returned.'''
        pass

    def cleanup_memory(self, force: bool=False) -> None:
        '''Memory is released through garbage collection and CUDA cache emptying operations.'''
        pass

    def get_optimal_training_config(self) -> Dict[str, Any]:
        '''Recommended model training configurations are retrieved based on detected hardware capabilities.'''
        pass

    def optimize_model_for_training(self, model):
        '''PyTorch's built-in memory optimization techniques for training execution are applied.'''
        pass

    def optimize_training_args(self, training_args):
        '''Training arguments are configured to optimize memory utilization during model training.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using synonymous language without changing any technical specifications, requirements, or behaviors._

---

## 9. RealClassEval/csn/snippet_52 — `llm_terse_01` (terse)

**Original**

```python
class BitField:
    '''Convert an integer to a string for each bit.'''

    def __init__(self, *names):
        '''Initialize the list of named bits.'''
        pass

    def __call__(self, val):
        '''Return a list with a string for each True bit in the integer.'''
        pass
```

**Rewrite**

```python
class BitField:
    '''Integer to bit strings conversion'''

    def __init__(self, *names):
        '''Named bits list initialization'''
        pass

    def __call__(self, val):
        '''List of strings for True bits'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings are concise rephrasings of the original requirements without changing the meaning of behavior, parameters, or return values._

---

## 10. RealClassEval/csn/snippet_13 — `llm_lexical_01` (lexical)

**Original**

```python

class velocity:
    '''
    Simulates the velocity of a dissipative soliton (kind of self organized particle) [6]_.
    The equilibrium velocity without noise R=0 for
    $    au>1.0/\kappa_3$ is $\kappa_3 \sqrt{(tau - 1.0/\kappa_3)/Q}.
    Before the drift-bifurcation $    au \le 1.0/\kappa_3$ the velocity is zero.
    References
    ----------
    .. [6] Andreas Kempa-Liehr (2013, p. 159-170)
        Dynamics of Dissipative Soliton
        Dissipative Solitons in Reaction Diffusion Systems.
        Springer: Berlin

    >>> ds = velocity(tau=3.5) # Dissipative soliton with equilibrium velocity 1.5e-3
    >>> print(ds.label) # Discriminating before or beyond Drift-Bifurcation
    1
    # Equilibrium velocity
    >>> print(ds.deterministic)
    0.0015191090506254991
    # Simulated velocity as a time series with 20000 time steps being disturbed by Gaussian white noise
    >>> v = ds.simulate(20000)
    '''

    def __init__(self, tau=3.8, kappa_3=0.3, Q=1950.0, R=0.0003, delta_t=0.05, seed=None):
        '''
        :param tau: Bifurcation parameter determining the intrinsic velocity of the dissipative soliton,
                    which is zero for tau<=1.0/kappa_3 and np.sqrt(kappa_3**3/Q * (tau - 1.0/kappa_3)) otherwise
        :type tau: float
        :param kappa_3: Inverse bifurcation point.
        :type kappa_3:
        :param Q: Shape parameter of dissipative soliton
        :type Q: float
        :param R: Noise amplitude
        :type R: float
        :param delta_t: temporal discretization
        :type delta_t: float
        '''
        pass

    def __call__(self, v):
        '''
        returns deterministic dynamic = acceleration (without noise)
        :param v: initial velocity vector
        :rtype v: ndarray
        :return: velocity vector of next time step
        :return type: ndarray
        '''
        pass

    def simulate(self, N, v0=np.zeros(2)):
        '''
        :param N: number of time steps
        :type N: int
        :param v0: initial velocity vector
        :type v0: ndarray
        :return: time series of velocity vectors with shape (N, v0.shape[0])
        :rtype: ndarray
        '''
        pass
```

**Rewrite**

```python

class velocity:
    '''
    Models the velocity of a dissipative soliton, a self-organized particle [6]_.
    In the absence of noise (R=0), the equilibrium velocity equals $\kappa_3 \sqrt{(tau - 1.0/\kappa_3)/Q}$ when the bifurcation parameter $au$ surpasses $1.0/\kappa_3$.
    For $au$ values at or below the drift-bifurcation limit $1.0/\kappa_3$, the equilibrium velocity remains zero.
    References
    ----------
    .. [6] Andreas Kempa-Liehr (2013, p. 159-170)
        Dynamics of Dissipative Soliton
        Dissipative Solitons in Reaction Diffusion Systems.
        Springer: Berlin

    >>> ds = velocity(tau=3.5) # Dissipative soliton with equilibrium velocity 1.5e-3
    >>> print(ds.label) # Discriminating before or beyond Drift-Bifurcation
    1
    # Equilibrium velocity
    >>> print(ds.deterministic)
    0.0015191090506254991
    # Simulated velocity as a time series with 20000 time steps being disturbed by Gaussian white noise
    >>> v = ds.simulate(20000)
    '''

    def __init__(self, tau=3.8, kappa_3=0.3, Q=1950.0, R=0.0003, delta_t=0.05, seed=None):
        '''
        :param tau: The bifurcation parameter governing the soliton's intrinsic motion speed. Velocity becomes zero when tau is less than or equal to 1.0/kappa_3, otherwise it computes to np.sqrt(kappa_3**3/Q * (tau - 1.0/kappa_3)).
        :type tau: float
        :param kappa_3: Inverse bifurcation point.
        :type kappa_3:
        :param Q: Shape parameter of dissipative soliton
        :type Q: float
        :param R: Noise amplitude
        :type R: float
        :param delta_t: temporal discretization interval
        :type delta_t: float
        '''
        pass

    def __call__(self, v):
        '''
        outputs deterministic acceleration excluding noise effects
        :param v: initial velocity vector
        :rtype v: ndarray
        :return: velocity vector corresponding to the immediate subsequent time step
        :return type: ndarray
        '''
        pass

    def simulate(self, N, v0=np.zeros(2)):
        '''
        :param N: total time steps to generate
        :type N: int
        :param v0: starting velocity vector
        :type v0: ndarray
        :return: sequence of velocity vectors spanning N steps with dimensions (N, v0.shape[0])
        :rtype: ndarray
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses different wording but preserves all mathematical conditions, parameter meanings, and example behaviors exactly._

---

## 11. RealClassEval/csn/snippet_54 — `llm_formal_01` (formal)

**Original**

```python
class Enum:
    '''Map values to specific strings.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the mapping.'''
        pass

    def __call__(self, val):
        '''Map an integer to the string representation.'''
        pass
```

**Rewrite**

```python
class Enum:
    '''Values are mapped to specific strings by this class.'''

    def __init__(self, *args, **kwargs):
        '''The mapping is initialized by this method.'''
        pass

    def __call__(self, val):
        '''An integer is mapped to the string representation by this method.'''
        pass
```

_judge: EQUIVALENT — The passive voice in the rewritten docstrings conveys the same core requirements without changing any technical specifications or behavior._

---

## 12. RealClassEval/post_cut-off/snippet_228 — `llm_formal_01` (formal)

**Original**

```python

class ClipboardService:
    '''Service for interacting with the system clipboard.'''

    def __init__(self):
        '''Initialize the clipboard service.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write text content to the clipboard.
        Args:
            content: Text content to write to clipboard
        Returns:
            Dict containing success status and any error information
        '''
        pass

    def _create_temp_file_from_image(self, image: Image.Image) -> Optional[str]:
        '''
        Create a temporary file from a PIL Image.
        Args:
            image: PIL Image object
        Returns:
            Path to the temporary file or None if failed
        '''
        pass

    def read(self) -> Dict[str, Any]:
        '''
        Read content from the clipboard and automatically determine the content type.
        Returns:
            Dict containing the clipboard content or error information
        '''
        pass

    def read_and_process_paste(self) -> Dict[str, Any]:
        '''
        Read clipboard content and if it's an image or binary file, create a temporary file
        and return a file command that can be processed.
        Returns:
            Dict containing either processed file command or regular text content
        '''
        pass

    def cleanup_temp_files(self):
        '''Clean up any temporary files created by this service.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write content to the clipboard.
        Args:
            content: Content to write to clipboard
        Returns:
            Dict containing success status and any error information
        '''
        pass

    def __del__(self):
        '''Cleanup temporary files when the service is destroyed.'''
        pass
```

**Rewrite**

```python

class ClipboardService:
    '''Provides functionality for interacting with the system clipboard.'''

    def __init__(self):
        '''Initializes the clipboard service upon instantiation.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Text content is written to the system clipboard. The argument 'content' shall be a string. The method returns a dictionary containing a success status and error information.
        '''
        pass

    def _create_temp_file_from_image(self, image: Image.Image) -> Optional[str]:
        '''
        A temporary file is created from a provided PIL Image object. The argument 'image' shall be an instance of the PIL Image class. The method returns the path to the temporary file if successful, otherwise returns None.
        '''
        pass

    def read(self) -> Dict[str, Any]:
        '''
        The system clipboard is read and the content type is automatically determined. The method returns a dictionary containing the clipboard content or error information.
        '''
        pass

    def read_and_process_paste(self) -> Dict[str, Any]:
        '''
        The system clipboard is read. If the retrieved content is an image or binary file, a temporary file is created and a file command that can be processed is returned; otherwise, the regular text content is returned directly. The method returns a dictionary containing either a processed file command or the regular text content.
        '''
        pass

    def cleanup_temp_files(self):
        '''All temporary files created by the service are removed.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        The system clipboard is written with the provided content. The argument 'content' shall be a string. The method returns a dictionary containing a success status and error information.
        '''
        pass

    def __del__(self):
        '''Temporary files created by the service are removed upon destruction of the service instance.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings clarify implicit requirements (e.g., specifying 'content' must be a string) without altering the core behavior, constraints, or outcomes described in the original._

---

## 13. RealClassEval/csn/snippet_11 — `llm_lexical_01` (lexical)

**Original**

```python

class AESModeCTR:
    '''Wrapper around pyaes.AESModeOfOperationCTR mode with custom IV'''

    def __init__(self, key, iv):
        '''
        Initializes the AES CTR mode with the given key/iv pair.
        :param key: the key to be used as bytes.
        :param iv: the bytes initialization vector. Must have a length of 16.
        '''
        pass

    def encrypt(self, data):
        '''
        Encrypts the given plain text through AES CTR.
        :param data: the plain text to be encrypted.
        :return: the encrypted cipher text.
        '''
        pass

    def decrypt(self, data):
        '''
        Decrypts the given cipher text through AES CTR
        :param data: the cipher text to be decrypted.
        :return: the decrypted plain text.
        '''
        pass
```

**Rewrite**

```python

class AESModeCTR:
    '''Provides an interface to pyaes.AESModeOfOperationCTR using externally supplied initialization vectors'''

    def __init__(self, key, iv):
        '''
        Configures the AES CTR mode with the specified cryptographic key and initialization vector pair.
        :param key: the cryptographic key provided in bytes format.
        :param iv: the initialization vector in bytes; must be exactly 16 bytes long.
        '''
        pass

    def encrypt(self, data):
        '''
        Performs encryption of the designated plaintext utilizing AES in CTR mode.
        :param data: the input plaintext data requiring encryption.
        :return: the resulting ciphertext output from the operation.
        '''
        pass

    def decrypt(self, data):
        '''
        Decrypts the supplied ciphertext through AES cipher in CTR mode.
        :param data: the ciphertext data needing decryption.
        :return: the original plaintext reconstructed from decryption.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing without changing functional requirements, parameter types, or behavioral constraints._

---

## 14. RealClassEval/csn/snippet_52 — `llm_formal_01` (formal)

**Original**

```python
class BitField:
    '''Convert an integer to a string for each bit.'''

    def __init__(self, *names):
        '''Initialize the list of named bits.'''
        pass

    def __call__(self, val):
        '''Return a list with a string for each True bit in the integer.'''
        pass
```

**Rewrite**

```python
class BitField:
    '''An integer value is converted into multiple strings, one for each bit.'''

    def __init__(self, *names):
        '''The list of named bits is initialized.'''
        pass

    def __call__(self, val):
        '''A list is returned containing a string for each set bit of the integer.'''
        pass
```

_judge: EQUIVALENT — The docstrings rephrase the same behavioral requirements without altering the meaning of inputs, outputs, or core functionality._

---

## 15. RealClassEval/csn/snippet_117 — `llm_lexical_01` (lexical)

**Original**

```python

class PDE:
    '''
    Representation of a partial differential equation.
    '''

    def __init__(self, lhs, rhs, bcs):
        '''
        Initializes the PDE.
        You need to specify the left hand side (lhs) in terms of derivatives
        as well as the right hand side in terms of an array.
        Parameters
        ----------
        lhs: FinDiff object or combination of FinDiff objects
            the left hand side of the PDE
        rhs: numpy.ndarray
            the right hand side of the PDE
        bcs: BoundaryConditions
            the boundary conditions for the PDE
        '''
        pass

    def solve(self):
        '''
        Solves the PDE.
        Returns
        -------
        out: numpy.ndarray
            Array with the solution of the PDE.
        '''
        pass
```

**Rewrite**

```python

class PDE:
    '''
    Modeling a partial differential equation.
    '''

    def __init__(self, lhs, rhs, bcs):
        '''
        Establishes a PDE instance.
        The left hand side (lhs) must be defined via derivative operators,
        and the right hand side (rhs) must be supplied as an array.
        Parameters
        ----------
        lhs: FinDiff object or combination of FinDiff objects
            represents the left-hand side expression of the PDE
        rhs: numpy.ndarray
            represents the right-hand side expression of the PDE
        bcs: BoundaryConditions
            specifies the boundary conditions for the PDE
        '''
        pass

    def solve(self):
        '''
        Computes the solution of the PDE.
        Returns
        -------
        out: numpy.ndarray
            The solution array of the PDE.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing ("Initializes" vs "Establishes", "Solves" vs "Computes the solution") and rewords parameter descriptions without changing any requirements, types, or behaviors._

---

## 16. RealClassEval/post_cut-off/snippet_4 — `llm_terse_01` (terse)

**Original**

```python

class MemoryManager:
    '''Simple memory manager that leverages PyTorch's built-in memory optimizations.'''

    def __init__(self):
        '''Initialize the memory manager.'''
        pass

    def get_memory_info(self) -> Dict[str, Any]:
        '''Get current memory usage information.'''
        pass

    def cleanup_memory(self, force: bool=False) -> None:
        '''Free up memory by garbage collection and emptying CUDA cache.'''
        pass

    def get_optimal_training_config(self) -> Dict[str, Any]:
        '''Get recommended configurations for model training based on hardware capabilities.'''
        pass

    def optimize_model_for_training(self, model):
        '''Apply PyTorch's built-in memory optimizations for training.'''
        pass

    def optimize_training_args(self, training_args):
        '''Configure training arguments for efficient memory usage.'''
        pass
```

**Rewrite**

```python

class MemoryManager:
    '''PyTorch memory optimizer'''

    def __init__(self):
        '''Memory manager initializer'''
        pass

    def get_memory_info(self) -> Dict[str, Any]:
        '''Current memory usage'''
        pass

    def cleanup_memory(self, force: bool=False) -> None:
        '''GC and CUDA cache release'''
        pass

    def get_optimal_training_config(self) -> Dict[str, Any]:
        '''Hardware-aware training configs'''
        pass

    def optimize_model_for_training(self, model):
        '''PyTorch training memory optimizations'''
        pass

    def optimize_training_args(self, training_args):
        '''Efficient memory training arguments'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use more concise phrasing but retain identical requirements, argument types, return values, and behavioral intent for all methods._

---

## 17. RealClassEval/post_cut-off/snippet_25 — `llm_terse_01` (terse)

**Original**

```python

class URLExtractor:
    '''URL提取器'''
    @staticmethod
    def convert_arxiv_url(url: str) -> str:
        '''将arXiv网页链接转换为PDF下载链接'''
        pass
    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        '''从文本中提取URL'''
        pass
    @staticmethod
    def infer_filename_from_url(url: str) -> str:
        '''从URL推断文件名'''
        pass
```

**Rewrite**

```python

class URLExtractor:
    '''URL extractor'''
    @staticmethod
    def convert_arxiv_url(url: str) -> str:
        '''Convert arXiv URL to PDF URL'''
        pass
    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        '''Extract URLs from text'''
        pass
    @staticmethod
    def infer_filename_from_url(url: str) -> str:
        '''Infer filename from URL'''
        pass
```

_judge: EQUIVALENT — The docstrings are translated from Chinese to English but describe identical behavior without changing requirements, types, or examples._

---

## 18. RealClassEval/post_cut-off/snippet_3 — `llm_formal_01` (formal)

**Original**

```python
@dataclass
class StatusBioDTO:
    '''Status biography data transfer object'''
    @classmethod
    def from_model(cls, model: 'StatusBiography') -> 'StatusBioDTO':
        '''Create DTO from database model
        Args:
            model (StatusBiography): database model object
        Returns:
            StatusBioDTO: data transfer object
        '''
        pass

    def to_dict(self) -> dict:
        '''Convert to dictionary format
        Returns:
            dict: dictionary format data
        '''
        pass
```

**Rewrite**

```python
@dataclass
class StatusBioDTO:
    '''A data transfer object for status biography data.'''
    @classmethod
    def from_model(cls, model: 'StatusBiography') -> 'StatusBioDTO':
        '''A data transfer object is constructed from a database model.
        Args:
            model: a StatusBiography object representing the source database model
        Returns:
            the constructed StatusBioDTO instance
        '''
        pass

    def to_dict(self) -> dict:
        '''A dictionary representation of the data transfer object is generated.
        Returns:
            a dictionary representation of the DTO
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and adds clarifying details without changing the core requirements, types, or behavior described in the original docstrings._

---

## 19. RealClassEval/post_cut-off/snippet_4 — `llm_lexical_01` (lexical)

**Original**

```python

class MemoryManager:
    '''Simple memory manager that leverages PyTorch's built-in memory optimizations.'''

    def __init__(self):
        '''Initialize the memory manager.'''
        pass

    def get_memory_info(self) -> Dict[str, Any]:
        '''Get current memory usage information.'''
        pass

    def cleanup_memory(self, force: bool=False) -> None:
        '''Free up memory by garbage collection and emptying CUDA cache.'''
        pass

    def get_optimal_training_config(self) -> Dict[str, Any]:
        '''Get recommended configurations for model training based on hardware capabilities.'''
        pass

    def optimize_model_for_training(self, model):
        '''Apply PyTorch's built-in memory optimizations for training.'''
        pass

    def optimize_training_args(self, training_args):
        '''Configure training arguments for efficient memory usage.'''
        pass
```

**Rewrite**

```python

class MemoryManager:
    '''A fundamental utility for handling memory resources through PyTorch's native memory optimization mechanisms.'''

    def __init__(self):
        '''Construct and initialize the memory manager instance.'''
        pass

    def get_memory_info(self) -> Dict[str, Any]:
        '''Retrieve details about the current memory consumption.'''
        pass

    def cleanup_memory(self, force: bool=False) -> None:
        '''Release unused resources via garbage collection and clearing the CUDA cache.'''
        pass

    def get_optimal_training_config(self) -> Dict[str, Any]:
        '''Provide suggested training setups tailored to the available hardware specifications.'''
        pass

    def optimize_model_for_training(self, model):
        '''Implement PyTorch's built-in memory optimization features specifically during model training.'''
        pass

    def optimize_training_args(self, training_args):
        '''Adjust training parameters to maximize memory efficiency during model training.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using synonymous language without changing any technical specifications, argument types, return values, or behavioral expectations._

---

## 20. RealClassEval/post_cut-off/snippet_293 — `llm_lexical_01` (lexical)

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
    Lightweight wrapper for sklearn's NearestNeighbors class to perform cosine similarity searches.
    :ivar model: A fitted NearestNeighbors instance.
    :vartype model: NearestNeighbors
    '''

    def __init__(self, items, k=3):
        '''
        Initialize the KNN index.
        :param items: An iterable providing (item_id, embedding_vector) pairs.
        :type items: Iterable[Tuple[Any, Sequence[float]]]
        :param k: The default count of neighbors to fetch.
        :type k: int
        '''
        pass

    def neighbors(self, target_emb, k=None):
        '''
        Find the k closest items using cosine distance.
        :param target_emb: The query embedding vector.
        :type target_emb: Sequence[float]
        :param k: Number of neighbors to return instead of the default (defaults to self.k).
        :type k: int
        :return: A list of (item_id, distance) tuples sorted by closeness.
        :rtype: List[Tuple[Any, float]]
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing (e.g., "lightweight" vs "thin", "proximity" vs "closeness") without changing any technical requirements, types, or behavioral constraints._

---

## 21. RealClassEval/post_cut-off/snippet_64 — `llm_formal_01` (formal)

**Original**

```python
class BaseTool:
    '''
    A base class for building tool classes that perform specific tasks, such as image processing or text detection.
        '''

    def __init__(self, tool_name=None, tool_description=None, tool_version=None, input_types=None, output_type=None, demo_commands=None, output_dir=None, user_metadata=None, model_string=None):
        '''
        Initialize the base tool with optional metadata.
        Parameters:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool.
            tool_version (str): The version of the tool.
            input_types (dict): The expected input types for the tool.
            output_type (str): The expected output type for the tool.
            demo_commands (list): A list of example commands for using the tool.
            output_dir (str): The directory where the tool should save its output (optional).
            user_metadata (dict): Additional metadata specific to user needs (optional).
            model_string (str): The model string for the LLM engine (optional, only used if require_llm_engine is True).
        '''
        pass

    def set_metadata(self, tool_name, tool_description, tool_version, input_types, output_type, demo_commands, user_metadata=None):
        '''
        Set the metadata for the tool.
        Parameters:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool.
            tool_version (str): The version of the tool.
            input_types (dict): The expected input types for the tool.
            output_type (str): The expected output type for the tool.
            demo_commands (list): A list of example commands for using the tool.
            user_metadata (dict): Additional metadata specific to user needs (optional).
        '''
        pass

    def get_metadata(self):
        '''
        Returns the metadata for the tool.
        Returns:
            dict: A dictionary containing the tool's metadata.
        '''
        pass

    def set_custom_output_dir(self, output_dir):
        '''
        Set a custom output directory for the tool.
        Parameters:
            output_dir (str): The new output directory path.
        '''
        pass

    def set_llm_engine(self, model_string):
        '''
        Set the LLM engine for the tool.
        Parameters:
            model_string (str): The model string for the LLM engine.
        '''
        pass

    def execute(self, *args, **kwargs):
        '''
        Execute the tool's main functionality. This method should be overridden by subclasses.
        Raises:
            NotImplementedError: If the subclass does not implement this method.
        '''
        pass
```

**Rewrite**

```python
class BaseTool:
    '''
    This class defines a base template for tool classes implementing designated computational operations, such as image processing or text detection.
        '''

    def __init__(self, tool_name=None, tool_description=None, tool_version=None, input_types=None, output_type=None, demo_commands=None, output_dir=None, user_metadata=None, model_string=None):
        '''
        The method configures the base tool instance by assigning optional metadata attributes.
        Parameters:
            tool_name: a string value denoting the name of the tool.
            tool_description: a string value describing the tool.
            tool_version: a string value specifying the version of the tool.
            input_types: a dictionary specifying the expected input data types for the tool.
            output_type: a string specifying the expected output data type for the tool.
            demo_commands: a list containing example command strings for tool usage.
            output_dir: a string specifying the directory path for saving tool output; this parameter is optional.
            user_metadata: a dictionary containing additional metadata for user-specific requirements; this parameter is optional.
            model_string: a string specifying the model identifier for the LLM engine; this parameter is optional and only used when require_llm_engine is True.
        '''
        pass

    def set_metadata(self, tool_name, tool_description, tool_version, input_types, output_type, demo_commands, user_metadata=None):
        '''
        The method assigns metadata attributes to the tool instance.
        Parameters:
            tool_name: a string value denoting the name of the tool.
            tool_description: a string value providing a description of the tool.
            tool_version: a string value indicating the version of the tool.
            input_types: a dictionary specifying the expected input data types for the tool.
            output_type: a string specifying the expected output data type for the tool.
            demo_commands: a list containing example command strings for tool usage.
            user_metadata: a dictionary containing additional metadata for user-specific requirements; this parameter is optional.
        '''
        pass

    def get_metadata(self):
        '''
        The method returns a dictionary object containing the tool's metadata.
        '''
        pass

    def set_custom_output_dir(self, output_dir):
        '''
        The method sets a custom output directory path for the tool.
        Parameters:
            output_dir: a string value specifying the new directory path for tool output.
        '''
        pass

    def set_llm_engine(self, model_string):
        '''
        The method sets the language model engine for the tool.
        Parameters:
            model_string: a string value specifying the model identifier for the LLM engine.
        '''
        pass

    def execute(self, *args, **kwargs):
        '''
        The method executes the tool's primary operational functionality. Subclasses are expected to override this method to provide concrete implementation. If a subclass does not override this method, invoking it will raise a NotImplementedError.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases descriptions without altering requirements, parameter meanings, optional status, or behavior specifications._

---

## 22. RealClassEval/csn/snippet_12 — `llm_lexical_01` (lexical)

**Original**

```python

class Factorization:
    '''
    Simple module to factorize large numbers really quickly.
    '''
    @classmethod
    def factorize(cls, pq):
        '''
        Factorizes the given large integer.
        Implementation from https://comeoncodeon.wordpress.com/2010/09/18/pollard-rho-brent-integer-factorization/.
        :param pq: the prime pair pq.
        :return: a tuple containing the two factors p and q.
        '''
        pass
    @staticmethod
    def gcd(a, b):
        '''
        Calculates the Greatest Common Divisor.
        :param a: the first number.
        :param b: the second number.
        :return: GCD(a, b)
        '''
        pass
```

**Rewrite**

```python

class Factorization:
    '''
    A basic Python module designed for the swift factorization of large integers.
    '''
    @classmethod
    def factorize(cls, pq):
        '''
        Computes the two prime factors of the input large integer.
        Based on the algorithm from https://comeoncodeon.wordpress.com/2010/09/18/pollard-rho-brent-integer-factorization.
        :param pq: the product of two prime numbers.
        :return: a tuple containing the two integer factors p and q.
        '''
        pass
    @staticmethod
    def gcd(a, b):
        '''
        Calculates the greatest common divisor (GCD) between two integers.
        :param a: the first integer.
        :param b: the second integer.
        :return: the greatest common divisor of a and b
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and clarifies terminology (e.g., "prime pair" to "product of two prime numbers") without altering the core requirements, parameter types, or expected behavior._

---

## 23. RealClassEval/post_cut-off/snippet_18 — `llm_lexical_01` (lexical)

**Original**

```python

class RetrievalResult:
    '''
    Represents a result retrieved from the vector database.
    This class encapsulates the information about a retrieved document,
    including its embedding, text content, reference, metadata, and similarity score.
    Attributes:
        embedding: The vector embedding of the document.
        text: The text content of the document.
        reference: A reference to the source of the document.
        metadata: Additional metadata associated with the document.
        score: The similarity score of the document to the query.
    '''

    def __init__(self, embedding: np.array, text: str, reference: str, metadata: dict, score: float=0.0):
        '''
        Initialize a RetrievalResult object.
        Args:
            embedding: The vector embedding of the document.
            text: The text content of the document.
            reference: A reference to the source of the document.
            metadata: Additional metadata associated with the document.
            score: The similarity score of the document to the query. Defaults to 0.0.
        '''
        pass

    def __repr__(self):
        '''
        Return a string representation of the RetrievalResult.
        Returns:
            A string representation of the RetrievalResult object.
        '''
        pass
```

**Rewrite**

```python

class RetrievalResult:
    '''
    Signifies a document acquired through vector database lookup.
    This class captures essential details of a single retrieved record,
    comprising its vector embedding, textual content, source reference, metadata, and similarity score.
    Attributes:
        embedding: The vector embedding of the document.
        text: The text content of the document.
        reference: A reference to the source of the document.
        metadata: Additional metadata associated with the document.
        score: The similarity score of the document to the query.
    '''

    def __init__(self, embedding: np.array, text: str, reference: str, metadata: dict, score: float=0.0):
        '''
        Initializes a new RetrievalResult instance.
        Arguments:
            embedding: The vector embedding of the document.
            text: The text content of the document.
            reference: A reference to the source of the document.
            metadata: Additional metadata associated with the document.
            score: The similarity score of the document to the query; defaults to 0.0.
        '''
        pass

    def __repr__(self):
        '''
        Delivers a string-based depiction of the RetrievalResult instance.
        Returns:
            A string representation of the RetrievalResult object.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing and minor clarifications (e.g., "vector embedding" instead of "embedding") without changing the meaning of requirements, types, arguments, or behavior._

---

## 24. RealClassEval/csn/snippet_110 — `llm_terse_01` (terse)

**Original**

```python
class Enum:
    '''
    Object supporting CircuitPython-style of static symbols
    as seen with Direction.OUTPUT, Pull.UP
    '''

    def __repr__(self):
        '''
        Assumes instance will be found as attribute of own class.
        Returns dot-subscripted path to instance
        (assuming absolute import of containing package)
        '''
        pass
    @classmethod
    def iteritems(cls):
        '''
        Inspects attributes of the class for instances of the class
        and returns as key,value pairs mirroring dict#iteritems
        '''
        pass
```

**Rewrite**

```python
class Enum:
    '''
    CircuitPython-style static symbol container
    '''

    def __repr__(self):
        '''
        Assumes own class attribute. Returns absolute dot-path
        '''
        pass
    @classmethod
    def iteritems(cls):
        '''
        Finds class instance attributes. Returns name/instance pairs
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements without changing, adding, or weakening any behavioral specifications or constraints._

---

## 25. RealClassEval/csn/snippet_13 — `llm_formal_01` (formal)

**Original**

```python

class velocity:
    '''
    Simulates the velocity of a dissipative soliton (kind of self organized particle) [6]_.
    The equilibrium velocity without noise R=0 for
    $    au>1.0/\kappa_3$ is $\kappa_3 \sqrt{(tau - 1.0/\kappa_3)/Q}.
    Before the drift-bifurcation $    au \le 1.0/\kappa_3$ the velocity is zero.
    References
    ----------
    .. [6] Andreas Kempa-Liehr (2013, p. 159-170)
        Dynamics of Dissipative Soliton
        Dissipative Solitons in Reaction Diffusion Systems.
        Springer: Berlin

    >>> ds = velocity(tau=3.5) # Dissipative soliton with equilibrium velocity 1.5e-3
    >>> print(ds.label) # Discriminating before or beyond Drift-Bifurcation
    1
    # Equilibrium velocity
    >>> print(ds.deterministic)
    0.0015191090506254991
    # Simulated velocity as a time series with 20000 time steps being disturbed by Gaussian white noise
    >>> v = ds.simulate(20000)
    '''

    def __init__(self, tau=3.8, kappa_3=0.3, Q=1950.0, R=0.0003, delta_t=0.05, seed=None):
        '''
        :param tau: Bifurcation parameter determining the intrinsic velocity of the dissipative soliton,
                    which is zero for tau<=1.0/kappa_3 and np.sqrt(kappa_3**3/Q * (tau - 1.0/kappa_3)) otherwise
        :type tau: float
        :param kappa_3: Inverse bifurcation point.
        :type kappa_3:
        :param Q: Shape parameter of dissipative soliton
        :type Q: float
        :param R: Noise amplitude
        :type R: float
        :param delta_t: temporal discretization
        :type delta_t: float
        '''
        pass

    def __call__(self, v):
        '''
        returns deterministic dynamic = acceleration (without noise)
        :param v: initial velocity vector
        :rtype v: ndarray
        :return: velocity vector of next time step
        :return type: ndarray
        '''
        pass

    def simulate(self, N, v0=np.zeros(2)):
        '''
        :param N: number of time steps
        :type N: int
        :param v0: initial velocity vector
        :type v0: ndarray
        :return: time series of velocity vectors with shape (N, v0.shape[0])
        :rtype: ndarray
        '''
        pass
```

**Rewrite**

```python

class velocity:
    '''
    Simulates the velocity of a dissipative soliton in dissipative systems.
    The equilibrium velocity without noise (R=0) is kappa_3 multiplied by the square root of (tau minus 1.0 divided by kappa_3, divided by Q) when tau exceeds 1.0 divided by kappa_3.
    For tau less than or equal to 1.0 divided by kappa_3, the equilibrium velocity is zero.
    >>> ds = velocity(tau=3.5) # Dissipative soliton with equilibrium velocity 1.5e-3
    >>> print(ds.label) # Discriminating before or beyond Drift-Bifurcation
    1
    # Equilibrium velocity
    >>> print(ds.deterministic)
    0.0015191090506254991
    # Simulated velocity as a time series with 20000 time steps being disturbed by Gaussian white noise
    >>> v = ds.simulate(20000)
    '''

    def __init__(self, tau=3.8, kappa_3=0.3, Q=1950.0, R=0.0003, delta_t=0.05, seed=None):
        '''
        tau: Bifurcation parameter determining the intrinsic velocity of the dissipative soliton. The equilibrium velocity is zero when tau is less than or equal to 1.0 divided by kappa_3. Otherwise, the equilibrium velocity is kappa_3 cubed multiplied by (tau minus 1.0 divided by kappa_3), divided by Q, and the square root of the resulting product.
        kappa_3: Inverse bifurcation point.
        Q: Shape parameter of the dissipative soliton.
        R: Amplitude of the noise.
        delta_t: Temporal discretization interval.
        '''
        pass

    def __call__(self, v):
        '''
        The method returns the deterministic acceleration without noise at the subsequent time step.
        v: Initial velocity vector provided as an array.
        The return value is an array representing the velocity vector at the next time step.
        '''
        pass

    def simulate(self, N, v0=np.zeros(2)):
        '''
        N: Number of time steps for simulation.
        v0: Initial velocity vector provided as an array.
        The return value is a two-dimensional array containing the time series of velocity vectors with shape (N, v0.shape[0]).
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases the docstrings in plain English without changing the mathematical requirements, parameter descriptions, or example behavior._

---

## 26. RealClassEval/csn/snippet_3 — `llm_lexical_01` (lexical)

**Original**

```python

class Serializable:
    '''This is the superclass of all serializable objects.'''

    def save(self, out_file):
        '''Save the model to the given file stream.'''
        pass
    @classmethod
    def load(cls, in_file, instantiate=True):
        '''This is meant to be overridden by subclasses and called with super.
        We return constructor argument values when not being instantiated. Since there are no
        constructor arguments for the Serializable class we just return an empty dictionary.
        '''
        pass
    @classmethod
    def _instantiated_load(cls, in_file, **kwargs):
        '''This is meant to be overridden by subclasses and called with super.
        We return constructor argument values (we have no values to load in this abstract class).
        '''
        pass
```

**Rewrite**

```python

class Serializable:
    '''This class functions as the foundational base for all entities supporting serialization.'''

    def save(self, out_file):
        '''Persist the model data to the specified file stream.'''
        pass
    @classmethod
    def load(cls, in_file, instantiate=True):
        '''Subclasses must override this method and invoke it using super().
        It supplies constructor argument values during non-instantiation loads; since Serializable defines no such parameters, an empty dictionary is returned.
        '''
        pass
    @classmethod
    def _instantiated_load(cls, in_file, **kwargs):
        '''Derived classes should implement this method and call it via super().
        It delivers constructor arguments for inspection when not creating an instance; however, lacking any parameters itself, it provides none.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing (e.g., "superclass" vs "foundational base", "save" vs "persist", "must override" vs "meant to be overridden") without changing any technical requirements, types, or behaviors._

---

## 27. RealClassEval/csn/snippet_117 — `llm_terse_01` (terse)

**Original**

```python

class PDE:
    '''
    Representation of a partial differential equation.
    '''

    def __init__(self, lhs, rhs, bcs):
        '''
        Initializes the PDE.
        You need to specify the left hand side (lhs) in terms of derivatives
        as well as the right hand side in terms of an array.
        Parameters
        ----------
        lhs: FinDiff object or combination of FinDiff objects
            the left hand side of the PDE
        rhs: numpy.ndarray
            the right hand side of the PDE
        bcs: BoundaryConditions
            the boundary conditions for the PDE
        '''
        pass

    def solve(self):
        '''
        Solves the PDE.
        Returns
        -------
        out: numpy.ndarray
            Array with the solution of the PDE.
        '''
        pass
```

**Rewrite**

```python

class PDE:
    '''
    PDE representation
    '''

    def __init__(self, lhs, rhs, bcs):
        '''
        PDE initializer
        Parameters:
        lhs: FinDiff or FinDiff combination (left-hand side operator)
        rhs: ndarray (right-hand side array)
        bcs: BoundaryConditions (boundary conditions)
        '''
        pass

    def solve(self):
        '''
        Solves PDE
        Returns out: ndarray (solution array)
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses concise language and standard abbreviations (e.g., "ndarray" for "numpy.ndarray") without changing the meaning of requirements, parameter types, or return values._

---

## 28. RealClassEval/csn/snippet_277 — `llm_lexical_01` (lexical)

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

## 29. RealClassEval/post_cut-off/snippet_5 — `llm_terse_01` (terse)

**Original**

```python

class ScriptRunner:
    '''Script executor, supports executing Python and Bash scripts'''

    def __init__(self, log_path: str='data/local_logs/train.log'):
        '''
        Initialize script executor
        Args:
            log_path: Base path for log files
        '''
        pass

    def _prepare_log_file(self, script_type: str) -> str:
        '''
        Prepare log file
        Args:
            script_type: Script type, used for log directory naming
        Returns:
            str: Complete path to the log file
        '''
        pass

    def _check_execution_env(self) -> Dict[str, str]:
        '''
        Get current execution environment information, supporting docker or regular system environment
        Returns:
            Dict[str, str]: Dictionary containing environment type and detailed information
        '''
        pass

    def _check_python_version(self) -> str:
        '''
        Get Python version information
        Returns:
            str: Python version information
        '''
        pass

    def execute_script(self, script_path: str, script_type: str, is_python: bool=False, args: Optional[list]=None) -> Dict[str, Any]:
        '''
        Execute script
        Args:
            script_path: Complete path to the script
            script_type: Script type, used for log directory naming
            is_python: Whether it is a Python script
            args: List of additional script parameters
        Returns:
            Dict[str, Any]: Execution result, including process ID, environment information and log file path
        '''
        pass
```

**Rewrite**

```python

class ScriptRunner:
    '''Executes Python and Bash scripts'''

    def __init__(self, log_path: str='data/local_logs/train.log'):
        '''
        Initialize ScriptRunner
        Args:
            log_path: log file base path
        '''
        pass

    def _prepare_log_file(self, script_type: str) -> str:
        '''
        Prepare log path
        Args:
            script_type: log dir naming parameter
        Returns:
            log file path
        '''
        pass

    def _check_execution_env(self) -> Dict[str, str]:
        '''
        Retrieve environment info (docker/system)
        Returns:
            env details dict
        '''
        pass

    def _check_python_version(self) -> str:
        '''
        Get Python version
        Returns:
            python version string
        '''
        pass

    def execute_script(self, script_path: str, script_type: str, is_python: bool=False, args: Optional[list]=None) -> Dict[str, Any]:
        '''
        Execute script
        Args:
            script_path: script file path
            script_type: log dir naming parameter
            is_python: Python script flag
            args: script arguments list
        Returns:
            execution result dict (pid, env info, log path)
        '''
        pass
```

_judge: EQUIVALENT — All requirements, argument types, and return value descriptions remain semantically identical despite minor rewording of terms and phrasing._

---

## 30. RealClassEval/csn/snippet_62 — `llm_terse_01` (terse)

**Original**

```python

class ReadWriteLock:
    '''Read-Write lock class. A read-write lock differs from a standard
    threading.RLock() by allowing multiple threads to simultaneously hold a
    read lock, while allowing only a single thread to hold a write lock at the
    same point of time.
    When a read lock is requested while a write lock is held, the reader
    is blocked; when a write lock is requested while another write lock is
    held or there are read locks, the writer is blocked.
    Writers are always preferred by this implementation: if there are blocked
    threads waiting for a write lock, current readers may request more read
    locks (which they eventually should free, as they starve the waiting
    writers otherwise), but a new thread requesting a read lock will not
    be granted one, and block. This might mean starvation for readers if
    two writer threads interweave their calls to acquire_write() without
    leaving a window only for readers.
    In case a current reader requests a write lock, this can and will be
    satisfied without giving up the read locks first, but, only one thread
    may perform this kind of lock upgrade, as a deadlock would otherwise
    occur. After the write lock has been granted, the thread will hold a
    full write lock, and not be downgraded after the upgrading call to
    acquire_write() has been match by a corresponding release().
    '''

    def __init__(self):
        '''Initialize this read-write lock.'''
        pass

    def acquire_read(self, *, timeout=None):
        '''Acquire a read lock for the current thread, waiting at most
        timeout seconds or doing a non-blocking check in case timeout is <= 0.
        In case timeout is None, the call to acquire_read blocks until the
        lock request can be serviced.
        In case the timeout expires before the lock could be serviced, a
        RuntimeError is thrown.'''
        pass

    def acquire_write(self, *, timeout=None):
        '''Acquire a write lock for the current thread, waiting at most
        timeout seconds or doing a non-blocking check in case timeout is <= 0.
        In case the write lock cannot be serviced due to the deadlock
        condition mentioned above, a ValueError is raised.
        In case timeout is None, the call to acquire_write blocks until the
        lock request can be serviced.
        In case the timeout expires before the lock could be serviced, a
        RuntimeError is thrown.'''
        pass

    def release(self):
        '''Release the currently held lock.
        In case the current thread holds no lock, a ValueError is thrown.'''
        pass
```

**Rewrite**

```python

class ReadWriteLock:
    '''Read-write lock: multiple read locks / single write lock. Writers preferred: new reads blocked if write-waiters. One reader may upgrade to write without releasing reads (only one upgrade at a time); lock remains write until release.
    '''

    def __init__(self):
        '''Initialize read-write lock.'''
        pass

    def acquire_read(self, *, timeout=None):
        '''Acquire read lock; block until acquired (None=infinite, <=0=non-blocking). RuntimeError if timeout expired.'''
        pass

    def acquire_write(self, *, timeout=None):
        '''Acquire write lock; ValueError if another write lock held or read locks exist. Block until acquired (None=infinite, <=0=non-blocking). RuntimeError if timeout expired.'''
        pass

    def release(self):
        '''Release lock held by current thread. ValueError if none.'''
        pass
```

_judge: EQUIVALENT — The rewrite condenses the original's detailed explanations into concise statements without altering any requirements, error conditions, or behavioral semantics._

---

## 31. RealClassEval/post_cut-off/snippet_309 — `llm_formal_01` (formal)

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
    '''Local blob storage implemented using the file system.'''

    def __init__(self, root: str | None=None, janitor_after_h: int=24):
        '''
        Initialize an instance of the local file-based blob storage.
        Args:
            root: Path to the root directory for blob storage. If unspecified, the environment variable BLOB_STORE_PATH is used or the directory defaults to 'blobs' relative to the current working directory.
            janitor_after_h: Duration in hours after which stored blobs become eligible for cleanup by the janitor process.
        '''
        pass

    def _path(self, blob_id: str) -> str:
        '''Retrieve the absolute file path of the binary data file associated with the specified blob identifier.'''
        pass

    def _meta_path(self, blob_id: str) -> str:
        '''Retrieve the absolute file path of the metadata file associated with the specified blob identifier.'''
        pass

    def save(self, data: bytes, meta: dict[str, Any]) -> str:
        '''
        Store binary data along with its metadata.
        Args:
            data: Binary payload to persist.
            meta: Dictionary containing supplementary metadata.
        Returns:
            Identifier of the stored blob, unique within the storage instance.
        '''
        pass

    def load(self, blob_id: str) -> bytes:
        '''
        Retrieve binary data by its blob identifier.
        Args:
            blob_id: Identifier of the blob to access.
        Returns:
            Binary data corresponding to the specified blob identifier.
        Raises:
            FileNotFoundError: When no blob exists matching the provided identifier.
        '''
        pass

    def info(self, blob_id: str) -> dict[str, Any]:
        '''
        Retrieve the metadata dictionary for a blob by identifier.
        Args:
            blob_id: Identifier of the blob.
        Returns:
            Dictionary containing the metadata associated with the blob.
        Raises:
            FileNotFoundError: When no blob exists matching the provided identifier.
        '''
        pass

    def delete(self, blob_id: str) -> None:
        '''
        Delete the blob and its metadata by identifier.
        Args:
            blob_id: Identifier of the blob to remove.
        '''
        pass

    def purge_old(self) -> None:
        '''Remove blobs whose creation time exceeds the configured janitor threshold duration.'''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses equivalent wording and clarifying details without changing any requirements, types, arguments, return values, or behavior._

---

## 32. RealClassEval/post_cut-off/snippet_18 — `llm_formal_01` (formal)

**Original**

```python

class RetrievalResult:
    '''
    Represents a result retrieved from the vector database.
    This class encapsulates the information about a retrieved document,
    including its embedding, text content, reference, metadata, and similarity score.
    Attributes:
        embedding: The vector embedding of the document.
        text: The text content of the document.
        reference: A reference to the source of the document.
        metadata: Additional metadata associated with the document.
        score: The similarity score of the document to the query.
    '''

    def __init__(self, embedding: np.array, text: str, reference: str, metadata: dict, score: float=0.0):
        '''
        Initialize a RetrievalResult object.
        Args:
            embedding: The vector embedding of the document.
            text: The text content of the document.
            reference: A reference to the source of the document.
            metadata: Additional metadata associated with the document.
            score: The similarity score of the document to the query. Defaults to 0.0.
        '''
        pass

    def __repr__(self):
        '''
        Return a string representation of the RetrievalResult.
        Returns:
            A string representation of the RetrievalResult object.
        '''
        pass
```

**Rewrite**

```python

class RetrievalResult:
    '''
    Encapsulates information pertaining to a single document retrieved from a vector database.
    The following attributes are defined:
        embedding: vector embedding of the document,
        text: text content of the document,
        reference: source reference of the document,
        metadata: additional metadata associated with the document,
        score: similarity score of the document relative to the query.
    '''

    def __init__(self, embedding: np.array, text: str, reference: str, metadata: dict, score: float=0.0):
        '''
        Initializes an instance of the RetrievalResult class with specified attribute values.
        Required parameters are embedding (vector embedding of the document), text (text content of the document), reference (source reference of the document), and metadata (additional metadata associated with the document).
        The parameter score (similarity score of the document relative to the query) is optional with a default value of 0.0.
        '''
        pass

    def __repr__(self):
        '''
        Produces a string representation of the RetrievalResult object.
        The method returns a string that represents the object.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite clarifies attribute descriptions and parameter roles without changing any requirements, types, or behavioral expectations._

---

## 33. RealClassEval/post_cut-off/snippet_64 — `llm_lexical_01` (lexical)

**Original**

```python
class BaseTool:
    '''
    A base class for building tool classes that perform specific tasks, such as image processing or text detection.
        '''

    def __init__(self, tool_name=None, tool_description=None, tool_version=None, input_types=None, output_type=None, demo_commands=None, output_dir=None, user_metadata=None, model_string=None):
        '''
        Initialize the base tool with optional metadata.
        Parameters:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool.
            tool_version (str): The version of the tool.
            input_types (dict): The expected input types for the tool.
            output_type (str): The expected output type for the tool.
            demo_commands (list): A list of example commands for using the tool.
            output_dir (str): The directory where the tool should save its output (optional).
            user_metadata (dict): Additional metadata specific to user needs (optional).
            model_string (str): The model string for the LLM engine (optional, only used if require_llm_engine is True).
        '''
        pass

    def set_metadata(self, tool_name, tool_description, tool_version, input_types, output_type, demo_commands, user_metadata=None):
        '''
        Set the metadata for the tool.
        Parameters:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool.
            tool_version (str): The version of the tool.
            input_types (dict): The expected input types for the tool.
            output_type (str): The expected output type for the tool.
            demo_commands (list): A list of example commands for using the tool.
            user_metadata (dict): Additional metadata specific to user needs (optional).
        '''
        pass

    def get_metadata(self):
        '''
        Returns the metadata for the tool.
        Returns:
            dict: A dictionary containing the tool's metadata.
        '''
        pass

    def set_custom_output_dir(self, output_dir):
        '''
        Set a custom output directory for the tool.
        Parameters:
            output_dir (str): The new output directory path.
        '''
        pass

    def set_llm_engine(self, model_string):
        '''
        Set the LLM engine for the tool.
        Parameters:
            model_string (str): The model string for the LLM engine.
        '''
        pass

    def execute(self, *args, **kwargs):
        '''
        Execute the tool's main functionality. This method should be overridden by subclasses.
        Raises:
            NotImplementedError: If the subclass does not implement this method.
        '''
        pass
```

**Rewrite**

```python
class BaseTool:
    '''
    Fundamental class intended for constructing specialized operational classes capable of handling distinct functions, including visual data manipulation or textual content identification.
        '''

    def __init__(self, tool_name=None, tool_description=None, tool_version=None, input_types=None, output_type=None, demo_commands=None, output_dir=None, user_metadata=None, model_string=None):
        '''
        Establishes the foundational tool instance using optional configuration parameters.
        Parameters:
            tool_name (str): The tool's designated identifier.
            tool_description (str): A textual explanation of the tool's intended purpose.
            tool_version (str): The current version string assigned to the tool.
            input_types (dict): Mapping of expected input data types to their structural specifications.
            output_type (str): The anticipated data type resulting from the tool's operation.
            demo_commands (list): Representative command examples illustrating the tool's usage.
            output_dir (str): Destination folder path for saving generated outputs (optional).
            user_metadata (dict): Supplementary user-defined contextual information (optional).
            model_string (str): Identifier string for the large language model engine (optional, applicable only when require_llm_engine is True).
        '''
        pass

    def set_metadata(self, tool_name, tool_description, tool_version, input_types, output_type, demo_commands, user_metadata=None):
        '''
        Configures the tool's metadata attributes based on provided values.
        Parameters:
            tool_name (str): The tool's assigned identifier.
            tool_description (str): A textual explanation of the tool's intended purpose.
            tool_version (str): The current version string assigned to the tool.
            input_types (dict): Mapping of expected input data types to their structural specifications.
            output_type (str): The anticipated data type resulting from the tool's operation.
            demo_commands (list): Representative command examples illustrating the tool's usage.
            user_metadata (dict): Supplementary user-defined contextual information (optional).
        '''
        pass

    def get_metadata(self):
        '''
        Provides the complete metadata dictionary associated with the tool.
        Returns:
            dict: A dictionary containing the tool's metadata.
        '''
        pass

    def set_custom_output_dir(self, output_dir):
        '''
        Assigns a user-specified path for storing the tool's output files.
        Parameters:
            output_dir (str): The new destination path for output storage.
        '''
        pass

    def set_llm_engine(self, model_string):
        '''
        Specifies the language model engine instance to be employed by the tool.
        Parameters:
            model_string (str): The model identifier string for the large language model engine.
        '''
        pass

    def execute(self, *args, **kwargs):
        '''
        Performs the primary operational logic of the tool. Subclasses are required to implement this method.
        Raises:
            NotImplementedError: If the subclass does not implement this method.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases the class and method docstrings with synonymous language (e.g., "building tool classes" → "constructing specialized operational classes", "perform specific tasks" → "capable of handling distinct functions") without altering any technical requirements, parameters, or behavioral _

---

## 34. RealClassEval/csn/snippet_129 — `llm_lexical_01` (lexical)

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
    '''Node in a Fenwick Tree.'''

    def __init__(self, parent, children, index=None):
        '''A Fenwick Tree node possessing exactly one parent and multiple children.
        :param FenwickNode parent: a parent node
        :param list(FenwickNode) children: a list of children nodes
        :param int index: node label
        '''
        pass

    def get_ancestors(self):
        '''Delivers the sequence of ancestor nodes belonging to the current instance. The ordering begins with the earliest ancestor.
        :return: node's ancestors, beginning with the most recent
        :rtype: list(FenwickNode)
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases requirements with synonymous language and identical contradictions in ancestor ordering without altering any behavioral constraints or specifications._

---

## 35. RealClassEval/post_cut-off/snippet_52 — `llm_lexical_01` (lexical)

**Original**

```python

class PSDConeProjection:
    '''
    Initial implementation of psd_cone_projection task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the PSDConeProjection.'''
        pass

    def solve(self, problem):
        '''
        Solve the psd_cone_projection problem.
        Args:
            problem: Dictionary containing problem data specific to psd_cone_projection
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

class PSDConeProjection:
    '''
    First version of the psd_cone_projection task implementation. OpenEvolve will later refine it for better performance and accuracy.
    '''

    def __init__(self):
        '''Establish the PSDConeProjection instance.'''
        pass

    def solve(self, problem):
        '''
        Address the psd_cone_projection problem.
        Args:
            problem: A dictionary holding data specific to the psd_cone_projection task
        Returns:
            A solution matching the task's required output format
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Verify if the supplied solution meets the problem's validity criteria.
        Args:
            problem: The initial problem definition
            solution: The candidate solution under evaluation
        Returns:
            Boolean confirmation of validity (True for valid, False for invalid)
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing without changing any requirements, argument types, return value semantics, or behavioral expectations._

---

## 36. RealClassEval/post_cut-off/snippet_293 — `llm_terse_01` (terse)

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
    Sklearn NearestNeighbors wrapper for cosine similarity
    :ivar model: Fitted NearestNeighbors
    :vartype model: NearestNeighbors
    :ivar k: Default neighbor count
    :vartype k: int
    '''

    def __init__(self, items, k=3):
        '''
        Initialize KNN index
        :param items: Item-embedding pairs
        :type items: Iterable[Tuple[Any, Sequence[float]]]
        :param k: Default neighbor count
        :type k: int
        '''
        pass

    def neighbors(self, target_emb, k=None):
        '''
        Retrieve k cosine-distance neighbors
        :param target_emb: Query embedding
        :type target_emb: Sequence[float]
        :param k: Override neighbor count (defaults to self.k)
        :type k: int
        :return: Proximity-sorted (item_id, distance) pairs
        :rtype: List[Tuple[Any, float]]
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing without altering any requirements, types, or behavioral semantics of the class or its methods._

---

## 37. RealClassEval/post_cut-off/snippet_5 — `llm_lexical_01` (lexical)

**Original**

```python

class ScriptRunner:
    '''Script executor, supports executing Python and Bash scripts'''

    def __init__(self, log_path: str='data/local_logs/train.log'):
        '''
        Initialize script executor
        Args:
            log_path: Base path for log files
        '''
        pass

    def _prepare_log_file(self, script_type: str) -> str:
        '''
        Prepare log file
        Args:
            script_type: Script type, used for log directory naming
        Returns:
            str: Complete path to the log file
        '''
        pass

    def _check_execution_env(self) -> Dict[str, str]:
        '''
        Get current execution environment information, supporting docker or regular system environment
        Returns:
            Dict[str, str]: Dictionary containing environment type and detailed information
        '''
        pass

    def _check_python_version(self) -> str:
        '''
        Get Python version information
        Returns:
            str: Python version information
        '''
        pass

    def execute_script(self, script_path: str, script_type: str, is_python: bool=False, args: Optional[list]=None) -> Dict[str, Any]:
        '''
        Execute script
        Args:
            script_path: Complete path to the script
            script_type: Script type, used for log directory naming
            is_python: Whether it is a Python script
            args: List of additional script parameters
        Returns:
            Dict[str, Any]: Execution result, including process ID, environment information and log file path
        '''
        pass
```

**Rewrite**

```python

class ScriptRunner:
    '''Handler for executing Python and Bash scripts'''

    def __init__(self, log_path: str='data/local_logs/train.log'):
        '''
        Constructor for the script executor
        Args:
            log_path: Destination path for log files
        '''
        pass

    def _prepare_log_file(self, script_type: str) -> str:
        '''
        Create log file entry
        Args:
            script_type: Classification of the script, which determines the log directory name
        Returns:
            str: Full system path for the log file
        '''
        pass

    def _check_execution_env(self) -> Dict[str, str]:
        '''
        Retrieve details about the current runtime environment, including Docker container or native system configuration
        Returns:
            Dict[str, str]: Mapping with environment category and specific configuration data
        '''
        pass

    def _check_python_version(self) -> str:
        '''
        Obtain the installed Python interpreter version
        Returns:
            str: String representation of the Python version
        '''
        pass

    def execute_script(self, script_path: str, script_type: str, is_python: bool=False, args: Optional[list]=None) -> Dict[str, Any]:
        '''
        Run the specified script
        Args:
            script_path: Full path to the script file to be executed
            script_type: Category of the script, influencing the log directory structure
            is_python: Boolean flag indicating if the script is written in Python
            args: Optional list of command-line parameters for the script
        Returns:
            Dict[str, Any]: Outcome containing process identifier, environment details, and generated log file path
        '''
        pass
```

_judge: EQUIVALENT — All wording changes use synonymous terms or clarify without altering functional requirements, arguments, return values, or behavior._

---

## 38. RealClassEval/post_cut-off/snippet_5 — `llm_formal_01` (formal)

**Original**

```python

class ScriptRunner:
    '''Script executor, supports executing Python and Bash scripts'''

    def __init__(self, log_path: str='data/local_logs/train.log'):
        '''
        Initialize script executor
        Args:
            log_path: Base path for log files
        '''
        pass

    def _prepare_log_file(self, script_type: str) -> str:
        '''
        Prepare log file
        Args:
            script_type: Script type, used for log directory naming
        Returns:
            str: Complete path to the log file
        '''
        pass

    def _check_execution_env(self) -> Dict[str, str]:
        '''
        Get current execution environment information, supporting docker or regular system environment
        Returns:
            Dict[str, str]: Dictionary containing environment type and detailed information
        '''
        pass

    def _check_python_version(self) -> str:
        '''
        Get Python version information
        Returns:
            str: Python version information
        '''
        pass

    def execute_script(self, script_path: str, script_type: str, is_python: bool=False, args: Optional[list]=None) -> Dict[str, Any]:
        '''
        Execute script
        Args:
            script_path: Complete path to the script
            script_type: Script type, used for log directory naming
            is_python: Whether it is a Python script
            args: List of additional script parameters
        Returns:
            Dict[str, Any]: Execution result, including process ID, environment information and log file path
        '''
        pass
```

**Rewrite**

```python

class ScriptRunner:
    '''The ScriptRunner class supports execution of Python and Bash scripts.'''

    def __init__(self, log_path: str='data/local_logs/train.log'):
        '''
        The __init__ method initializes the ScriptRunner instance. The log_path parameter specifies the base path for log files.
        '''
        pass

    def _prepare_log_file(self, script_type: str) -> str:
        '''
        The _prepare_log_file method returns the complete path to the log file as a string. The script_type parameter specifies the log directory name used for storage.
        '''
        pass

    def _check_execution_env(self) -> Dict[str, str]:
        '''
        The _check_execution_env method returns a dictionary containing the environment type and detailed environment information. The environment type indicates whether execution occurs within a Docker container or on the host system.
        '''
        pass

    def _check_python_version(self) -> str:
        '''
        The _check_python_version method returns a string containing the Python version information.
        '''
        pass

    def execute_script(self, script_path: str, script_type: str, is_python: bool=False, args: Optional[list]=None) -> Dict[str, Any]:
        '''
        The execute_script method executes the specified script and returns a dictionary with string keys and any values, containing the execution result. The script_path parameter specifies the complete path to the script file. The script_type parameter specifies the type used for log directory naming. The is_python parameter indicates whether the script is a Python script. The args parameter provides a list of additional script parameters. The returned dictionary includes the process identifier, environment information dictionary, and complete log file path.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses more descriptive phrasing but preserves all requirements, argument meanings, return value specifications, and behavioral expectations without adding, removing, or altering any constraints._

---

## 39. RealClassEval/csn/snippet_12 — `llm_formal_01` (formal)

**Original**

```python

class Factorization:
    '''
    Simple module to factorize large numbers really quickly.
    '''
    @classmethod
    def factorize(cls, pq):
        '''
        Factorizes the given large integer.
        Implementation from https://comeoncodeon.wordpress.com/2010/09/18/pollard-rho-brent-integer-factorization/.
        :param pq: the prime pair pq.
        :return: a tuple containing the two factors p and q.
        '''
        pass
    @staticmethod
    def gcd(a, b):
        '''
        Calculates the Greatest Common Divisor.
        :param a: the first number.
        :param b: the second number.
        :return: GCD(a, b)
        '''
        pass
```

**Rewrite**

```python

class Factorization:
    '''
    Provides functionality for the factorization of large integers.
    '''
    @classmethod
    def factorize(cls, pq):
        '''
        The input parameter pq must be a large integer that is the product of two prime numbers. The method returns a tuple (p, q) where p and q are prime numbers and p multiplied by q equals the input integer.
        '''
        pass
    @staticmethod
    def gcd(a, b):
        '''
        The parameters a and b must be integers. The method returns the greatest common divisor of a and b, defined as the largest positive integer that divides both a and b without remainder.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite clarifies and makes explicit the implicit requirements from the original docstrings without adding, dropping, or changing any functional requirements._

---

## 40. RealClassEval/csn/snippet_277 — `llm_formal_01` (formal)

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
    '''Class for immutable objects.'''

    def __init__(self, **kwargs: Any) -> None:
        '''Initializes the instance using the provided keyword arguments.'''
        pass

    def __setattr__(self, name: str, value: Any) -> None:
        '''Prevents setting of any instance attribute.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the requirements with more detail but do not change the core behavior, scope, or constraints defined in the original specification._

---

## 41. RealClassEval/csn/snippet_117 — `llm_formal_01` (formal)

**Original**

```python

class PDE:
    '''
    Representation of a partial differential equation.
    '''

    def __init__(self, lhs, rhs, bcs):
        '''
        Initializes the PDE.
        You need to specify the left hand side (lhs) in terms of derivatives
        as well as the right hand side in terms of an array.
        Parameters
        ----------
        lhs: FinDiff object or combination of FinDiff objects
            the left hand side of the PDE
        rhs: numpy.ndarray
            the right hand side of the PDE
        bcs: BoundaryConditions
            the boundary conditions for the PDE
        '''
        pass

    def solve(self):
        '''
        Solves the PDE.
        Returns
        -------
        out: numpy.ndarray
            Array with the solution of the PDE.
        '''
        pass
```

**Rewrite**

```python

class PDE:
    '''
    A representation of a partial differential equation is provided by the PDE class.
    '''

    def __init__(self, lhs, rhs, bcs):
        '''
        The initialization of a PDE instance requires the 'lhs' argument to be a FinDiff object or a combination of FinDiff objects, the 'rhs' argument to be a numpy.ndarray, and the 'bcs' argument to be a BoundaryConditions object.
        '''
        pass

    def solve(self):
        '''
        A numpy.ndarray containing the solution of the PDE is returned by the solve method.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases requirements without changing parameter types, return value semantics, or behavioral constraints._

---

## 42. RealClassEval/csn/snippet_28 — `llm_lexical_01` (lexical)

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
    Container for storing details pertaining to a distance calculation query.
    '''

    def __init__(self, names, result):
        '''
        Initialize the DistanceData instance using the two object names (in sequence) and the outcome of the distance computation between them.
        '''
        pass
    @property
    def distance(self):
        '''
        Provides the straight-line Euclidean separation between the two objects.
        '''
        pass

    def index(self, name):
        '''
        Returns the face index on the mesh identified by the specified name that is nearest to the other colliding entity.
        '''
        pass

    def point(self, name):
        '''
        The 3D position of the point on the mesh defined by the given name having minimal distance to the opposing object.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing without changing any requirement, parameter meaning, or behavior._

---

## 43. RealClassEval/post_cut-off/snippet_359 — `llm_terse_01` (terse)

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
    drfp fingerprint encoding utility
        '''
    @staticmethod
    def shingling_from_mol(in_mol: Mol, radius: int=3, rings: bool=True, min_radius: int=0, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[List[str], Tuple[List[str], Dict[str, List[Set[int]]]]]:
        '''Molecular shingling from RDKit Mol
        in_mol: RDKit Mol
        radius: drfp radius (3=drfp6)
        rings: include rings
        min_radius: min n-gram radius
        Returns:
        Molecular shingling
        '''
        pass
    @staticmethod
    def internal_encode(in_smiles: str, radius: int=3, min_radius: int=0, rings: bool=True, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Drfp array from reaction SMILES
        in_smiles: valid reaction SMILES
        radius: drfp radius (3=drfp6)
        min_radius: min n-gram radius
        rings: include rings
        Returns:
        Hash values array, substructure SMILES array
        '''
        pass
    @staticmethod
    def hash(shingling: List[str]) -> np.ndarray:
        '''32-bit integers from shingling SMILES
        shingling: list of n-grams
        Returns:
        List of hashed n-grams
        '''
        pass
    @staticmethod
    def fold(hash_values: np.ndarray, length: int=2048) -> Tuple[np.ndarray, np.ndarray]:
        '''Binary vector from hash values
        hash_value: hash values array
        length: fingerprint length
        Returns:
        Tuple of folded fingerprint, on bit indices
        '''
        pass
    @staticmethod
    def encode(X: Union[Iterable, str], n_folded_length: int=2048, min_radius: int=0, radius: int=3, rings: bool=True, mapping: bool=False, atom_index_mapping: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False, show_progress_bar: bool=False) -> Union[List[np.ndarray], Tuple[List[np.ndarray], Dict[int, Set[str]]], Tuple[List[np.ndarray], Dict[int, Set[str]]], List[Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''Drfp fingerprint encoding of reaction SMILES
        X: reaction SMILES iterable or single
        n_folded_length: folded fingerprint length (modulo hashing)
        min_radius: min substructure radius (0=single atoms)
        radius: max substructure radius
        rings: include full rings
        mapping: return feature mapping
        atom_index_mapping: return atom indices
        root_central_atom: root central atom in SMILES
        show_progress_bar: show progress bar
        Returns:
        Fingerprints list or tuple with mapping dict if mapping
        '''
        pass
```

_judge: EQUIVALENT — The rewrite only alters docstring phrasing and adds clarifying details to parameter descriptions without changing any requirements, types, arguments, return values, or behaviors._

---

## 44. RealClassEval/csn/snippet_28 — `llm_terse_01` (terse)

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
    Distance query data
    '''

    def __init__(self, names, result):
        '''
        Initialize DistanceData
        Parameters
        ----------
        names : list of str
          Names of two objects in order.
        contact : fcl.DistanceResult
          Distance query result.
        '''
        pass
    @property
    def distance(self):
        '''
        Returns distance between objects
        Returns
        -------
        distance : float
          Euclidean distance between objects.
        '''
        pass

    def index(self, name):
        '''
        Returns closest face index of target mesh
        Parameters
        ----------
        name : str
          Target object name.
        Returns
        -------
        index : int
          Index of closest face in collision.
        '''
        pass

    def point(self, name):
        '''
        Closest point on target mesh
        Parameters
        ----------
        name : str
          Target object name.
        Returns
        -------
        point : (3,) float
          3D closest point.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite only alters phrasing and register (e.g., removing articles like "the" and "a") without changing any requirements, parameters, return types, or examples._

---

## 45. RealClassEval/post_cut-off/snippet_18 — `llm_terse_01` (terse)

**Original**

```python

class RetrievalResult:
    '''
    Represents a result retrieved from the vector database.
    This class encapsulates the information about a retrieved document,
    including its embedding, text content, reference, metadata, and similarity score.
    Attributes:
        embedding: The vector embedding of the document.
        text: The text content of the document.
        reference: A reference to the source of the document.
        metadata: Additional metadata associated with the document.
        score: The similarity score of the document to the query.
    '''

    def __init__(self, embedding: np.array, text: str, reference: str, metadata: dict, score: float=0.0):
        '''
        Initialize a RetrievalResult object.
        Args:
            embedding: The vector embedding of the document.
            text: The text content of the document.
            reference: A reference to the source of the document.
            metadata: Additional metadata associated with the document.
            score: The similarity score of the document to the query. Defaults to 0.0.
        '''
        pass

    def __repr__(self):
        '''
        Return a string representation of the RetrievalResult.
        Returns:
            A string representation of the RetrievalResult object.
        '''
        pass
```

**Rewrite**

```python

class RetrievalResult:
    '''
    Vector database retrieval result
    Attributes:
        embedding: vector embedding
        text: document text
        reference: document reference
        metadata: document metadata
        score: similarity score
    '''

    def __init__(self, embedding: np.array, text: str, reference: str, metadata: dict, score: float=0.0):
        '''
        Initialize RetrievalResult
        embedding: vector embedding
        text: document text
        reference: document reference
        metadata: metadata dict
        score: similarity score (0.0 default)
        '''
        pass

    def __repr__(self):
        '''
        Returns string representation
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses more concise language but preserves identical requirements for attributes, initialization parameters, and method behaviors without altering technical specifications or meaning._

---

## 46. RealClassEval/post_cut-off/snippet_24 — `llm_terse_01` (terse)

**Original**

```python

class LocalPathExtractor:
    '''本地路径提取器'''
    @staticmethod
    def is_local_path(path: str) -> bool:
        '''判断是否为本地路径'''
        pass
    @staticmethod
    def extract_local_paths(text: str) -> List[str]:
        '''从文本中提取本地文件路径'''
        pass
```

**Rewrite**

```python

class LocalPathExtractor:
    '''Local path extractor'''
    @staticmethod
    def is_local_path(path: str) -> bool:
        '''Local path check'''
        pass
    @staticmethod
    def extract_local_paths(text: str) -> List[str]:
        '''Local file paths in text'''
        pass
```

_judge: EQUIVALENT — The docstrings use different languages and phrasing but describe identical requirements without altering technical specifications or behavior._

---

## 47. RealClassEval/csn/snippet_277 — `llm_terse_01` (terse)

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
    '''Immutability'''

    def __init__(self, **kwargs: Any) -> None:
        '''Initialization'''
        pass

    def __setattr__(self, name: str, value: Any) -> None:
        '''Mutability prevention'''
        pass
```

_judge: EQUIVALENT — The docstring wording changes (e.g., "Immutable." to "Immutability") do not alter the intended behavior or requirements of the class._

---

## 48. RealClassEval/csn/snippet_11 — `llm_terse_01` (terse)

**Original**

```python

class AESModeCTR:
    '''Wrapper around pyaes.AESModeOfOperationCTR mode with custom IV'''

    def __init__(self, key, iv):
        '''
        Initializes the AES CTR mode with the given key/iv pair.
        :param key: the key to be used as bytes.
        :param iv: the bytes initialization vector. Must have a length of 16.
        '''
        pass

    def encrypt(self, data):
        '''
        Encrypts the given plain text through AES CTR.
        :param data: the plain text to be encrypted.
        :return: the encrypted cipher text.
        '''
        pass

    def decrypt(self, data):
        '''
        Decrypts the given cipher text through AES CTR
        :param data: the cipher text to be decrypted.
        :return: the decrypted plain text.
        '''
        pass
```

**Rewrite**

```python

class AESModeCTR:
    '''pyaes.AESModeOfOperationCTR wrapper with custom IV'''

    def __init__(self, key, iv):
        '''
        Initializes AES CTR with key and 16-byte IV
        :param key: bytes key
        :param iv: 16-byte IV
        '''
        pass

    def encrypt(self, data):
        '''
        Encrypts plaintext via AES CTR
        :param data: plaintext
        :return: ciphertext
        '''
        pass

    def decrypt(self, data):
        '''
        Decrypts ciphertext via AES CTR
        :param data: ciphertext
        :return: plaintext
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses more concise phrasing but maintains identical requirements, parameter types, return values, and behavioral constraints for all methods._

---

## 49. RealClassEval/post_cut-off/snippet_3 — `llm_lexical_01` (lexical)

**Original**

```python
@dataclass
class StatusBioDTO:
    '''Status biography data transfer object'''
    @classmethod
    def from_model(cls, model: 'StatusBiography') -> 'StatusBioDTO':
        '''Create DTO from database model
        Args:
            model (StatusBiography): database model object
        Returns:
            StatusBioDTO: data transfer object
        '''
        pass

    def to_dict(self) -> dict:
        '''Convert to dictionary format
        Returns:
            dict: dictionary format data
        '''
        pass
```

**Rewrite**

```python
@dataclass
class StatusBioDTO:
    '''Data transfer object for status biography information'''
    @classmethod
    def from_model(cls, model: 'StatusBiography') -> 'StatusBioDTO':
        '''Constructs a DTO instance from a database model entity
        Args:
            model (StatusBiography): the database model instance
        Returns:
            StatusBioDTO: an instance of the data transfer object
        '''
        pass

    def to_dict(self) -> dict:
        '''Transforms the object into a dictionary representation
        Returns:
            dict: a dictionary containing the object's data
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses synonymous phrasing (e.g., "Constructs" vs "Create", "instance" vs "object") without changing any functional requirements, types, or behavioral specifications._

---

## 50. RealClassEval/post_cut-off/snippet_309 — `llm_lexical_01` (lexical)

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
    '''A file system backed storage solution for binary large objects.'''

    def __init__(self, root: str | None=None, janitor_after_h: int=24):
        '''
        Set up a new instance of the file-based blob storage system.
        Args:
            root: Base directory path for storing blobs (defaults to environment variable BLOB_STORE_PATH or the current working directory's 'blobs' subfolder).
            janitor_after_h: Interval in hours after which stored blobs become candidates for automatic cleanup
        '''
        pass

    def _path(self, blob_id: str) -> str:
        '''Retrieve the filesystem location where a blob's raw binary content is stored.'''
        pass

    def _meta_path(self, blob_id: str) -> str:
        '''Obtain the filesystem path to a blob's associated metadata file.'''
        pass

    def save(self, data: bytes, meta: dict[str, Any]) -> str:
        '''
        Persist binary data along with its accompanying metadata.
        Args:
            data: Raw byte sequence intended for storage
            meta: Dictionary containing associated metadata
        Returns:
            A newly generated identifier for the saved blob
        '''
        pass

    def load(self, blob_id: str) -> bytes:
        '''
        Fetch stored binary content using its unique identifier.
        Args:
            blob_id: Identifier of the blob to retrieve
        Returns:
            The binary data associated with the given blob ID
        Raises:
            FileNotFoundError: If no blob exists with the specified ID
        '''
        pass

    def info(self, blob_id: str) -> dict[str, Any]:
        '''
        Retrieve metadata information for a specific blob.
        Args:
            blob_id: Unique identifier of the blob
        Returns:
            Dictionary containing the blob's metadata
        Raises:
            FileNotFoundError: When the blob ID is not found in storage
        '''
        pass

    def delete(self, blob_id: str) -> None:
        '''
        Remove both the binary data file and its metadata from storage.
        Args:
            blob_id: Identifier of the blob to erase
        '''
        pass

    def purge_old(self) -> None:
        '''Eliminate all blob records that exceed the configured cleanup age limit.'''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing without changing any functional requirements, argument types, return values, or error conditions._

---

## 51. RealClassEval/csn/snippet_11 — `llm_formal_01` (formal)

**Original**

```python

class AESModeCTR:
    '''Wrapper around pyaes.AESModeOfOperationCTR mode with custom IV'''

    def __init__(self, key, iv):
        '''
        Initializes the AES CTR mode with the given key/iv pair.
        :param key: the key to be used as bytes.
        :param iv: the bytes initialization vector. Must have a length of 16.
        '''
        pass

    def encrypt(self, data):
        '''
        Encrypts the given plain text through AES CTR.
        :param data: the plain text to be encrypted.
        :return: the encrypted cipher text.
        '''
        pass

    def decrypt(self, data):
        '''
        Decrypts the given cipher text through AES CTR
        :param data: the cipher text to be decrypted.
        :return: the decrypted plain text.
        '''
        pass
```

**Rewrite**

```python

class AESModeCTR:
    '''Wrapper class around pyaes.AESModeOfOperationCTR mode using a custom initialization vector'''

    def __init__(self, key, iv):
        '''
        Initializes the AES CTR mode instance by configuring the key and initialization vector.
        :param key: a key provided as bytes
        :param iv: an initialization vector provided as bytes of length 16
        '''
        pass

    def encrypt(self, data):
        '''
        Encrypts the provided plaintext using the AES CTR mode.
        :param data: plaintext to be encrypted.
        :return: encrypted ciphertext.
        '''
        pass

    def decrypt(self, data):
        '''
        Decrypts the provided ciphertext using the AES CTR mode.
        :param data: ciphertext to be decrypted.
        :return: decrypted plaintext.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing (e.g., "plaintext" vs "plain text") without changing any requirements, parameter types, or behavioral expectations._

---

## 52. RealClassEval/csn/snippet_62 — `llm_formal_01` (formal)

**Original**

```python

class ReadWriteLock:
    '''Read-Write lock class. A read-write lock differs from a standard
    threading.RLock() by allowing multiple threads to simultaneously hold a
    read lock, while allowing only a single thread to hold a write lock at the
    same point of time.
    When a read lock is requested while a write lock is held, the reader
    is blocked; when a write lock is requested while another write lock is
    held or there are read locks, the writer is blocked.
    Writers are always preferred by this implementation: if there are blocked
    threads waiting for a write lock, current readers may request more read
    locks (which they eventually should free, as they starve the waiting
    writers otherwise), but a new thread requesting a read lock will not
    be granted one, and block. This might mean starvation for readers if
    two writer threads interweave their calls to acquire_write() without
    leaving a window only for readers.
    In case a current reader requests a write lock, this can and will be
    satisfied without giving up the read locks first, but, only one thread
    may perform this kind of lock upgrade, as a deadlock would otherwise
    occur. After the write lock has been granted, the thread will hold a
    full write lock, and not be downgraded after the upgrading call to
    acquire_write() has been match by a corresponding release().
    '''

    def __init__(self):
        '''Initialize this read-write lock.'''
        pass

    def acquire_read(self, *, timeout=None):
        '''Acquire a read lock for the current thread, waiting at most
        timeout seconds or doing a non-blocking check in case timeout is <= 0.
        In case timeout is None, the call to acquire_read blocks until the
        lock request can be serviced.
        In case the timeout expires before the lock could be serviced, a
        RuntimeError is thrown.'''
        pass

    def acquire_write(self, *, timeout=None):
        '''Acquire a write lock for the current thread, waiting at most
        timeout seconds or doing a non-blocking check in case timeout is <= 0.
        In case the write lock cannot be serviced due to the deadlock
        condition mentioned above, a ValueError is raised.
        In case timeout is None, the call to acquire_write blocks until the
        lock request can be serviced.
        In case the timeout expires before the lock could be serviced, a
        RuntimeError is thrown.'''
        pass

    def release(self):
        '''Release the currently held lock.
        In case the current thread holds no lock, a ValueError is thrown.'''
        pass
```

**Rewrite**

```python

class ReadWriteLock:
    '''A read-write lock class that permits concurrent read access by multiple threads while restricting write access to a single thread at any given time. Read lock requests are blocked when a write lock is held; write lock requests are blocked when any read lock or another write lock is held. Writer preference is enforced: existing read lock holders may acquire additional read locks when writers are pending, but new read lock requests are denied if writers are blocked, potentially causing reader starvation if writer threads continuously interleave acquire_write operations without permitting reader access windows. Read lock holders may upgrade to a write lock without releasing held reads, provided no other locks exist, with only one thread permitted to perform such an upgrade to prevent deadlock. Upon successful upgrade, the thread holds a write lock until release, and does not revert to a read lock after the upgrade operation is completed by a corresponding release call.
    '''

    def __init__(self):
        '''Initializes the read-write lock object.'''
        pass

    def acquire_read(self, *, timeout=None):
        '''A read lock is acquired by the calling thread. The operation waits for up to timeout seconds; if timeout is zero or negative, a non-blocking check is performed. The operation blocks until the read lock can be granted when timeout is None. A RuntimeError is raised if the specified timeout expires before the lock is granted.'''
        pass

    def acquire_write(self, *, timeout=None):
        '''A write lock is acquired by the calling thread. The operation waits for up to timeout seconds; if timeout is zero or negative, a non-blocking check is performed. The operation blocks until the write lock can be granted when timeout is None. A ValueError is raised if the write lock cannot be granted due to the deadlock condition described in the class documentation. A RuntimeError is raised if the specified timeout expires before the lock is granted.'''
        pass

    def release(self):
        '''The lock held by the calling thread is released. A ValueError is raised if the calling thread does not hold any lock.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings preserve all behavioral requirements, exception conditions, and lock semantics without altering specifications of parameters, return values, or critical constraints._

---

## 53. RealClassEval/post_cut-off/snippet_25 — `llm_formal_01` (formal)

**Original**

```python

class URLExtractor:
    '''URL提取器'''
    @staticmethod
    def convert_arxiv_url(url: str) -> str:
        '''将arXiv网页链接转换为PDF下载链接'''
        pass
    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        '''从文本中提取URL'''
        pass
    @staticmethod
    def infer_filename_from_url(url: str) -> str:
        '''从URL推断文件名'''
        pass
```

**Rewrite**

```python

class URLExtractor:
    '''Class providing utility functions for URL extraction from text and conversion of arXiv web URLs to PDF download links'''
    @staticmethod
    def convert_arxiv_url(url: str) -> str:
        '''An arXiv web URL is converted to the corresponding PDF download URL'''
        pass
    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        '''URLs are extracted from the input text'''
        pass
    @staticmethod
    def infer_filename_from_url(url: str) -> str:
        '''The filename is inferred from the URL'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements in English with equivalent meaning without altering specifications, types, or behaviors._

---

## 54. RealClassEval/csn/snippet_52 — `llm_lexical_01` (lexical)

**Original**

```python
class BitField:
    '''Convert an integer to a string for each bit.'''

    def __init__(self, *names):
        '''Initialize the list of named bits.'''
        pass

    def __call__(self, val):
        '''Return a list with a string for each True bit in the integer.'''
        pass
```

**Rewrite**

```python
class BitField:
    '''Create individual string representations for every bit of the input integer.'''

    def __init__(self, *names):
        '''Establish the list of named bit identifiers.'''
        pass

    def __call__(self, val):
        '''Output a list containing one string per set bit in the given integer.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings preserve the exact meaning of all requirements without adding, dropping, or altering any specification details._

---

## 55. RealClassEval/post_cut-off/snippet_3 — `llm_terse_01` (terse)

**Original**

```python
@dataclass
class StatusBioDTO:
    '''Status biography data transfer object'''
    @classmethod
    def from_model(cls, model: 'StatusBiography') -> 'StatusBioDTO':
        '''Create DTO from database model
        Args:
            model (StatusBiography): database model object
        Returns:
            StatusBioDTO: data transfer object
        '''
        pass

    def to_dict(self) -> dict:
        '''Convert to dictionary format
        Returns:
            dict: dictionary format data
        '''
        pass
```

**Rewrite**

```python
@dataclass
class StatusBioDTO:
    '''StatusBio DTO'''
    @classmethod
    def from_model(cls, model: 'StatusBiography') -> 'StatusBioDTO':
        '''Build DTO from model
        Args:
            model (StatusBiography):
        Returns:
            StatusBioDTO:
        '''
        pass

    def to_dict(self) -> dict:
        '''To dict
        Returns:
            dict:
        '''
        pass
```

_judge: EQUIVALENT — The rewrite shortens docstring wording and uses abbreviations without changing the core requirements or behavior specifications._

---

## 56. RealClassEval/post_cut-off/snippet_52 — `llm_terse_01` (terse)

**Original**

```python

class PSDConeProjection:
    '''
    Initial implementation of psd_cone_projection task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the PSDConeProjection.'''
        pass

    def solve(self, problem):
        '''
        Solve the psd_cone_projection problem.
        Args:
            problem: Dictionary containing problem data specific to psd_cone_projection
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

class PSDConeProjection:
    '''
    psd_cone_projection task
    '''

    def __init__(self):
        '''PSDConeProjection initialization'''
        pass

    def solve(self, problem):
        '''
        Solve psd_cone_projection problem
        Args:
          problem: psd_cone_projection dict
        Returns:
          psd_cone_projection solution
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        Validate psd_cone_projection solution
        Args:
          problem: psd_cone_projection problem
          solution: solution
        Returns:
          bool
        '''
        pass
```

_judge: EQUIVALENT — The docstring changes are purely stylistic rephrasing without altering functional requirements, argument types, return value semantics, or solution validation behavior._

---

## 57. RealClassEval/csn/snippet_3 — `llm_formal_01` (formal)

**Original**

```python

class Serializable:
    '''This is the superclass of all serializable objects.'''

    def save(self, out_file):
        '''Save the model to the given file stream.'''
        pass
    @classmethod
    def load(cls, in_file, instantiate=True):
        '''This is meant to be overridden by subclasses and called with super.
        We return constructor argument values when not being instantiated. Since there are no
        constructor arguments for the Serializable class we just return an empty dictionary.
        '''
        pass
    @classmethod
    def _instantiated_load(cls, in_file, **kwargs):
        '''This is meant to be overridden by subclasses and called with super.
        We return constructor argument values (we have no values to load in this abstract class).
        '''
        pass
```

**Rewrite**

```python

class Serializable:
    '''The Serializable class is the superclass of all serializable objects.'''

    def save(self, out_file):
        '''The model is saved to the given file stream.'''
        pass
    @classmethod
    def load(cls, in_file, instantiate=True):
        '''This method must be overridden by subclasses and called with super.
        When the instantiate parameter is false, the method returns the constructor argument values.
        For the Serializable class, which has no constructor arguments, the method returns an empty dictionary when the instantiate parameter is false.
        '''
        pass
    @classmethod
    def _instantiated_load(cls, in_file, **kwargs):
        '''This method must be overridden by subclasses and called with super.
        Constructor argument values are returned by the Serializable class, which has no constructor arguments.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite rephrases requirements with equivalent meaning (e.g., "is meant to be" vs "must" convey the same obligation for subclasses, and all conditional behaviors for `instantiate=False` and empty dictionary return are preserved)._

---

## 58. RealClassEval/csn/snippet_54 — `llm_terse_01` (terse)

**Original**

```python
class Enum:
    '''Map values to specific strings.'''

    def __init__(self, *args, **kwargs):
        '''Initialize the mapping.'''
        pass

    def __call__(self, val):
        '''Map an integer to the string representation.'''
        pass
```

**Rewrite**

```python
class Enum:
    '''Value-to-string mapping'''

    def __init__(self, *args, **kwargs):
        '''Mapping initialization'''
        pass

    def __call__(self, val):
        '''Integer string representation mapping'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous phrasing without altering any functional requirements, argument types, or behavioral specifications._

---

## 59. RealClassEval/post_cut-off/snippet_24 — `llm_formal_01` (formal)

**Original**

```python

class LocalPathExtractor:
    '''本地路径提取器'''
    @staticmethod
    def is_local_path(path: str) -> bool:
        '''判断是否为本地路径'''
        pass
    @staticmethod
    def extract_local_paths(text: str) -> List[str]:
        '''从文本中提取本地文件路径'''
        pass
```

**Rewrite**

```python

class LocalPathExtractor:
    '''Methods are provided to determine whether a string is a local file path and to extract local file paths from text.'''
    @staticmethod
    def is_local_path(path: str) -> bool:
        '''Whether the input is a local file path is determined.'''
        pass
    @staticmethod
    def extract_local_paths(text: str) -> List[str]:
        '''Local file paths are extracted from text.'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings rephrase the original requirements using passive voice and different wording but convey identical behavioral expectations for both methods and the class purpose._

---

## 60. RealClassEval/csn/snippet_110 — `llm_formal_01` (formal)

**Original**

```python
class Enum:
    '''
    Object supporting CircuitPython-style of static symbols
    as seen with Direction.OUTPUT, Pull.UP
    '''

    def __repr__(self):
        '''
        Assumes instance will be found as attribute of own class.
        Returns dot-subscripted path to instance
        (assuming absolute import of containing package)
        '''
        pass
    @classmethod
    def iteritems(cls):
        '''
        Inspects attributes of the class for instances of the class
        and returns as key,value pairs mirroring dict#iteritems
        '''
        pass
```

**Rewrite**

```python
class Enum:
    '''
    Defines static symbols in the CircuitPython enumeration style.
    '''

    def __repr__(self):
        '''
        The method returns a string representing the dot-separated path to the instance, assuming the instance is an attribute of its class and the containing package is imported absolutely.
        '''
        pass
    @classmethod
    def iteritems(cls):
        '''
        The method returns an iterator yielding (attribute_name, instance) tuples for each class attribute that is an instance of the class, mirroring the dict.iteritems() method.
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses more precise language without altering any requirement, type, or behavior described in the original specification._

---

## 61. RealClassEval/post_cut-off/snippet_309 — `llm_terse_01` (terse)

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
        Initialize(root: Blob storage root (default: env BLOB_STORE_PATH or CWD/blobs), janitor_after_h: Cleanup threshold hours)
        '''
        pass

    def _path(self, blob_id: str) -> str:
        '''Blob binary data path'''
        pass

    def _meta_path(self, blob_id: str) -> str:
        '''Blob metadata path'''
        pass

    def save(self, data: bytes, meta: dict[str, Any]) -> str:
        '''
        Save(data: bytes, meta: dict) -> unique blob ID
        '''
        pass

    def load(self, blob_id: str) -> bytes:
        '''
        Load(blob_id) -> bytes; Raises FileNotFoundError
        '''
        pass

    def info(self, blob_id: str) -> dict[str, Any]:
        '''
        Get(blob_id) -> dict
        '''
        pass

    def delete(self, blob_id: str) -> None:
        '''
        Delete(blob_id) -> None
        '''
        pass

    def purge_old(self) -> None:
        '''Purge blobs older than janitor threshold'''
        pass
```

_judge: EQUIVALENT — The rewrite condenses descriptions and uses type annotations without changing the meaning of requirements, argument types, return values, or behavior._

---

## 62. RealClassEval/post_cut-off/snippet_64 — `llm_terse_01` (terse)

**Original**

```python
class BaseTool:
    '''
    A base class for building tool classes that perform specific tasks, such as image processing or text detection.
        '''

    def __init__(self, tool_name=None, tool_description=None, tool_version=None, input_types=None, output_type=None, demo_commands=None, output_dir=None, user_metadata=None, model_string=None):
        '''
        Initialize the base tool with optional metadata.
        Parameters:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool.
            tool_version (str): The version of the tool.
            input_types (dict): The expected input types for the tool.
            output_type (str): The expected output type for the tool.
            demo_commands (list): A list of example commands for using the tool.
            output_dir (str): The directory where the tool should save its output (optional).
            user_metadata (dict): Additional metadata specific to user needs (optional).
            model_string (str): The model string for the LLM engine (optional, only used if require_llm_engine is True).
        '''
        pass

    def set_metadata(self, tool_name, tool_description, tool_version, input_types, output_type, demo_commands, user_metadata=None):
        '''
        Set the metadata for the tool.
        Parameters:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool.
            tool_version (str): The version of the tool.
            input_types (dict): The expected input types for the tool.
            output_type (str): The expected output type for the tool.
            demo_commands (list): A list of example commands for using the tool.
            user_metadata (dict): Additional metadata specific to user needs (optional).
        '''
        pass

    def get_metadata(self):
        '''
        Returns the metadata for the tool.
        Returns:
            dict: A dictionary containing the tool's metadata.
        '''
        pass

    def set_custom_output_dir(self, output_dir):
        '''
        Set a custom output directory for the tool.
        Parameters:
            output_dir (str): The new output directory path.
        '''
        pass

    def set_llm_engine(self, model_string):
        '''
        Set the LLM engine for the tool.
        Parameters:
            model_string (str): The model string for the LLM engine.
        '''
        pass

    def execute(self, *args, **kwargs):
        '''
        Execute the tool's main functionality. This method should be overridden by subclasses.
        Raises:
            NotImplementedError: If the subclass does not implement this method.
        '''
        pass
```

**Rewrite**

```python
class BaseTool:
    '''
    Base class for task-specific tool classes (image processing, text detection)
        '''

    def __init__(self, tool_name=None, tool_description=None, tool_version=None, input_types=None, output_type=None, demo_commands=None, output_dir=None, user_metadata=None, model_string=None):
        '''
        Initialize base tool with optional metadata.
        Parameters:
            tool_name (str): Tool name
            tool_description (str): Tool description
            tool_version (str): Tool version
            input_types (dict): Expected input types
            output_type (str): Expected output type
            demo_commands (list): Example commands
            output_dir (str): Output directory (optional)
            user_metadata (dict): User metadata (optional)
            model_string (str): LLM model string (optional if require_llm_engine)
        '''
        pass

    def set_metadata(self, tool_name, tool_description, tool_version, input_types, output_type, demo_commands, user_metadata=None):
        '''
        Set tool metadata.
        Parameters:
            tool_name (str): Tool name
            tool_description (str): Tool description
            tool_version (str): Tool version
            input_types (dict): Expected input types
            output_type (str): Expected output type
            demo_commands (list): Example commands
            user_metadata (dict): User metadata (optional)
        '''
        pass

    def get_metadata(self):
        '''
        Return tool metadata.
        Returns:
            dict: Tool metadata
        '''
        pass

    def set_custom_output_dir(self, output_dir):
        '''
        Set output directory.
        Parameters:
            output_dir (str): Output directory
        '''
        pass

    def set_llm_engine(self, model_string):
        '''
        Set LLM engine.
        Parameters:
            model_string (str): LLM model string
        '''
        pass

    def execute(self, *args, **kwargs):
        '''
        Execute tool functionality.
        Raises:
            NotImplementedError: Subclass must implement
        '''
        pass
```

_judge: EQUIVALENT — The rewrite uses concise phrasing without changing any requirement, parameter meaning, or behavioral specification._

---

## 63. RealClassEval/csn/snippet_12 — `llm_terse_01` (terse)

**Original**

```python

class Factorization:
    '''
    Simple module to factorize large numbers really quickly.
    '''
    @classmethod
    def factorize(cls, pq):
        '''
        Factorizes the given large integer.
        Implementation from https://comeoncodeon.wordpress.com/2010/09/18/pollard-rho-brent-integer-factorization/.
        :param pq: the prime pair pq.
        :return: a tuple containing the two factors p and q.
        '''
        pass
    @staticmethod
    def gcd(a, b):
        '''
        Calculates the Greatest Common Divisor.
        :param a: the first number.
        :param b: the second number.
        :return: GCD(a, b)
        '''
        pass
```

**Rewrite**

```python

class Factorization:
    '''
    Factorize large numbers quickly
    '''
    @classmethod
    def factorize(cls, pq):
        '''
        Factorize large integer
        Implements Pollard-Rho Brent
        :param pq: prime pair pq
        :return: tuple of two factors p, q
        '''
        pass
    @staticmethod
    def gcd(a, b):
        '''
        Compute GCD(a, b)
        :param a: first number
        :param b: second number
        :return: GCD(a, b)
        '''
        pass
```

_judge: EQUIVALENT — The docstrings describe identical functional requirements with only minor wording changes that do not alter meaning, behavior, or specifications._

---

## 64. RealClassEval/post_cut-off/snippet_24 — `llm_lexical_01` (lexical)

**Original**

```python

class LocalPathExtractor:
    '''本地路径提取器'''
    @staticmethod
    def is_local_path(path: str) -> bool:
        '''判断是否为本地路径'''
        pass
    @staticmethod
    def extract_local_paths(text: str) -> List[str]:
        '''从文本中提取本地文件路径'''
        pass
```

**Rewrite**

```python

class LocalPathExtractor:
    '''Identifier for local file system paths'''
    @staticmethod
    def is_local_path(path: str) -> bool:
        '''Checks if a provided path corresponds to a local file location'''
        pass
    @staticmethod
    def extract_local_paths(text: str) -> List[str]:
        '''Finds and retrieves all local file paths embedded within a text string'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use synonymous English phrasing without altering the core requirements, types, or behavior described in the original specification._

---

## 65. RealClassEval/csn/snippet_110 — `llm_lexical_01` (lexical)

**Original**

```python
class Enum:
    '''
    Object supporting CircuitPython-style of static symbols
    as seen with Direction.OUTPUT, Pull.UP
    '''

    def __repr__(self):
        '''
        Assumes instance will be found as attribute of own class.
        Returns dot-subscripted path to instance
        (assuming absolute import of containing package)
        '''
        pass
    @classmethod
    def iteritems(cls):
        '''
        Inspects attributes of the class for instances of the class
        and returns as key,value pairs mirroring dict#iteritems
        '''
        pass
```

**Rewrite**

```python
class Enum:
    '''
    This object enables CircuitPython-style static symbols, such as Direction.OUTPUT and Pull.UP.
    '''

    def __repr__(self):
        '''
        It presumes the instance is defined as an attribute of its parent class. The method generates a dotted-path string locating the instance (under the assumption of absolute package import).
        '''
        pass
    @classmethod
    def iteritems(cls):
        '''
        The method examines class attributes for objects that are instances of the class itself, producing key-value tuples analogous to dict.items() output.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification uses synonymous phrasing without changing any requirements, examples, or behavioral expectations from the original._

---

## 66. RealClassEval/post_cut-off/snippet_25 — `llm_lexical_01` (lexical)

**Original**

```python

class URLExtractor:
    '''URL提取器'''
    @staticmethod
    def convert_arxiv_url(url: str) -> str:
        '''将arXiv网页链接转换为PDF下载链接'''
        pass
    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        '''从文本中提取URL'''
        pass
    @staticmethod
    def infer_filename_from_url(url: str) -> str:
        '''从URL推断文件名'''
        pass
```

**Rewrite**

```python

class URLExtractor:
    '''A utility for extracting Uniform Resource Locators from diverse inputs'''
    @staticmethod
    def convert_arxiv_url(url: str) -> str:
        '''Transforms an arXiv article webpage address into the direct link for downloading its PDF version'''
        pass
    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        '''Scans provided text content and retrieves every embedded web address'''
        pass
    @staticmethod
    def infer_filename_from_url(url: str) -> str:
        '''Deduces the filename that would be generated when saving the resource referenced by the given URL'''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings use more descriptive language but convey identical requirements for each method without altering behavior, types, or examples._

---

## 67. RealClassEval/post_cut-off/snippet_228 — `llm_terse_01` (terse)

**Original**

```python

class ClipboardService:
    '''Service for interacting with the system clipboard.'''

    def __init__(self):
        '''Initialize the clipboard service.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write text content to the clipboard.
        Args:
            content: Text content to write to clipboard
        Returns:
            Dict containing success status and any error information
        '''
        pass

    def _create_temp_file_from_image(self, image: Image.Image) -> Optional[str]:
        '''
        Create a temporary file from a PIL Image.
        Args:
            image: PIL Image object
        Returns:
            Path to the temporary file or None if failed
        '''
        pass

    def read(self) -> Dict[str, Any]:
        '''
        Read content from the clipboard and automatically determine the content type.
        Returns:
            Dict containing the clipboard content or error information
        '''
        pass

    def read_and_process_paste(self) -> Dict[str, Any]:
        '''
        Read clipboard content and if it's an image or binary file, create a temporary file
        and return a file command that can be processed.
        Returns:
            Dict containing either processed file command or regular text content
        '''
        pass

    def cleanup_temp_files(self):
        '''Clean up any temporary files created by this service.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write content to the clipboard.
        Args:
            content: Content to write to clipboard
        Returns:
            Dict containing success status and any error information
        '''
        pass

    def __del__(self):
        '''Cleanup temporary files when the service is destroyed.'''
        pass
```

**Rewrite**

```python

class ClipboardService:
    '''Clipboard interaction service'''

    def __init__(self):
        '''Initialize service'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write clipboard text
        Args:
            content: clipboard text
        Returns:
            success status and error
        '''
        pass

    def _create_temp_file_from_image(self, image: Image.Image) -> Optional[str]:
        '''
        Create temp file from image
        Args:
            image: PIL Image
        Returns:
            temp file path or None
        '''
        pass

    def read(self) -> Dict[str, Any]:
        '''
        Read clipboard with auto type detection
        Returns:
            content or error
        '''
        pass

    def read_and_process_paste(self) -> Dict[str, Any]:
        '''
        Read clipboard, process images/binary to temp file
        Returns:
            file command or text
        '''
        pass

    def cleanup_temp_files(self):
        '''Cleanup temp files'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write clipboard content
        Args:
            content: clipboard text
        Returns:
            success status and error
        '''
        pass

    def __del__(self):
        '''temp cleanup on destruction'''
        pass
```

_judge: EQUIVALENT — All differences are minor rephrasings of the same requirements without altering meaning, types, or behavior._

---

## 68. RealClassEval/csn/snippet_13 — `llm_terse_01` (terse)

**Original**

```python

class velocity:
    '''
    Simulates the velocity of a dissipative soliton (kind of self organized particle) [6]_.
    The equilibrium velocity without noise R=0 for
    $    au>1.0/\kappa_3$ is $\kappa_3 \sqrt{(tau - 1.0/\kappa_3)/Q}.
    Before the drift-bifurcation $    au \le 1.0/\kappa_3$ the velocity is zero.
    References
    ----------
    .. [6] Andreas Kempa-Liehr (2013, p. 159-170)
        Dynamics of Dissipative Soliton
        Dissipative Solitons in Reaction Diffusion Systems.
        Springer: Berlin

    >>> ds = velocity(tau=3.5) # Dissipative soliton with equilibrium velocity 1.5e-3
    >>> print(ds.label) # Discriminating before or beyond Drift-Bifurcation
    1
    # Equilibrium velocity
    >>> print(ds.deterministic)
    0.0015191090506254991
    # Simulated velocity as a time series with 20000 time steps being disturbed by Gaussian white noise
    >>> v = ds.simulate(20000)
    '''

    def __init__(self, tau=3.8, kappa_3=0.3, Q=1950.0, R=0.0003, delta_t=0.05, seed=None):
        '''
        :param tau: Bifurcation parameter determining the intrinsic velocity of the dissipative soliton,
                    which is zero for tau<=1.0/kappa_3 and np.sqrt(kappa_3**3/Q * (tau - 1.0/kappa_3)) otherwise
        :type tau: float
        :param kappa_3: Inverse bifurcation point.
        :type kappa_3:
        :param Q: Shape parameter of dissipative soliton
        :type Q: float
        :param R: Noise amplitude
        :type R: float
        :param delta_t: temporal discretization
        :type delta_t: float
        '''
        pass

    def __call__(self, v):
        '''
        returns deterministic dynamic = acceleration (without noise)
        :param v: initial velocity vector
        :rtype v: ndarray
        :return: velocity vector of next time step
        :return type: ndarray
        '''
        pass

    def simulate(self, N, v0=np.zeros(2)):
        '''
        :param N: number of time steps
        :type N: int
        :param v0: initial velocity vector
        :type v0: ndarray
        :return: time series of velocity vectors with shape (N, v0.shape[0])
        :rtype: ndarray
        '''
        pass
```

**Rewrite**

```python

class velocity:
    '''
    Dissipative soliton velocity model [6]_: 0 for tau<=1/kappa_3 else kappa_3*sqrt((tau-1/kappa_3)/Q)
    >>> ds = velocity(tau=3.5) # Dissipative soliton with equilibrium velocity 1.5e-3
    >>> print(ds.label) # Discriminating before or beyond Drift-Bifurcation
    1
    # Equilibrium velocity
    >>> print(ds.deterministic)
    0.0015191090506254991
    # Simulated velocity as a time series with 20000 time steps being disturbed by Gaussian white noise
    >>> v = ds.simulate(20000)
    '''

    def __init__(self, tau=3.8, kappa_3=0.3, Q=1950.0, R=0.0003, delta_t=0.05, seed=None):
        '''
        tau: float determining intrinsic velocity (0 if tau<=1/kappa_3 else sqrt(kappa_3**3/Q*(tau-1/kappa_3)))
        kappa_3: inverse bifurcation point
        Q: soliton shape parameter (float)
        R: noise amplitude (float)
        delta_t: temporal discretization (float)
        '''
        pass

    def __call__(self, v):
        '''
        Deterministic next velocity: v (ndarray) -> v_next (ndarray)
        '''
        pass

    def simulate(self, N, v0=np.zeros(2)):
        '''
        N: int
        v0: ndarray
        Velocity time series (ndarray, shape (N, v0.shape[0])) from v0 (ndarray)
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification preserves all critical requirements (velocity conditions, parameter roles, return types, and examples) without altering mathematical conditions, types, or behavioral expectations._

---

## 69. RealClassEval/post_cut-off/snippet_359 — `llm_formal_01` (formal)

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
    The encoding of SMILES as drfp fingerprints is provided by this utility class.
        '''
    @staticmethod
    def shingling_from_mol(in_mol: Mol, radius: int=3, rings: bool=True, min_radius: int=0, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[List[str], Tuple[List[str], Dict[str, List[Set[int]]]]]:
        '''A molecular shingling is generated from an instance of rdkit.Chem.rdchem.Mol.
        in_mol: an instance of rdkit.Chem.rdchem.Mol
        radius: an integer; a value of 3 corresponds to drfp6
        rings: a boolean indicating whether rings are included in the shingling
        min_radius: an integer representing the minimum radius used for n-gram extraction
        Returns: the molecular shingling
        '''
        pass
    @staticmethod
    def internal_encode(in_smiles: str, radius: int=3, min_radius: int=0, rings: bool=True, get_atom_indices: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''An drfp array is created from a reaction SMILES string.
        in_smiles: a valid reaction SMILES string
        radius: an integer; a value of 3 corresponds to drfp6
        min_radius: an integer representing the minimum radius used for n-gram extraction
        rings: a boolean indicating whether rings are included in the shingling
        Returns: a tuple containing two arrays; the first array holds the drfp hash values and the second array holds the substructure SMILES
        '''
        pass
    @staticmethod
    def hash(shingling: List[str]) -> np.ndarray:
        '''All SMILES in a shingling are hashed to 32-bit integers.
        shingling: a list of n-grams
        Returns: a list of 32-bit integer hashes
        '''
        pass
    @staticmethod
    def fold(hash_values: np.ndarray, length: int=2048) -> Tuple[np.ndarray, np.ndarray]:
        '''The hash values are folded into a binary vector of a specified length.
        hash_value: an array containing hash values
        length: an integer specifying the length of the folded fingerprint
        Returns: a tuple containing the folded fingerprint and the indices of the on bits
        '''
        pass
    @staticmethod
    def encode(X: Union[Iterable, str], n_folded_length: int=2048, min_radius: int=0, radius: int=3, rings: bool=True, mapping: bool=False, atom_index_mapping: bool=False, root_central_atom: bool=True, include_hydrogens: bool=False, show_progress_bar: bool=False) -> Union[List[np.ndarray], Tuple[List[np.ndarray], Dict[int, Set[str]]], Tuple[List[np.ndarray], Dict[int, Set[str]]], List[Dict[str, List[Dict[str, List[Set[int]]]]]]]:
        '''A list of drfp fingerprints is generated for reaction SMILES.
        X: an iterable of reaction SMILES strings; or a single reaction SMILES string
        n_folded_length: an integer specifying the folded length of the fingerprint for modulo hashing
        min_radius: an integer representing the minimum radius of a substructure; a value of 0 includes single atoms
        radius: an integer representing the maximum radius of a substructure
        rings: a boolean indicating whether full rings are included as substructures
        mapping: a boolean indicating whether to return a feature to substructure mapping in addition to the fingerprints
        atom_index_mapping: a boolean indicating whether to return atom indices of mapped substructures for each reaction
        root_central_atom: a boolean indicating whether the central atom of substructures is rooted when generating SMILES
        show_progress_bar: a boolean indicating whether to display a progress bar during reaction encoding
        Returns: a list of drfp fingerprints; if mapping is enabled, a tuple containing a list of drfp fingerprints and a mapping dictionary
        '''
        pass
```

_judge: EQUIVALENT — The rewritten specification maintains identical requirements, types, arguments, return values, and behavior descriptions despite more concise phrasing in docstrings._

---

## 70. RealClassEval/post_cut-off/snippet_228 — `llm_lexical_01` (lexical)

**Original**

```python

class ClipboardService:
    '''Service for interacting with the system clipboard.'''

    def __init__(self):
        '''Initialize the clipboard service.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write text content to the clipboard.
        Args:
            content: Text content to write to clipboard
        Returns:
            Dict containing success status and any error information
        '''
        pass

    def _create_temp_file_from_image(self, image: Image.Image) -> Optional[str]:
        '''
        Create a temporary file from a PIL Image.
        Args:
            image: PIL Image object
        Returns:
            Path to the temporary file or None if failed
        '''
        pass

    def read(self) -> Dict[str, Any]:
        '''
        Read content from the clipboard and automatically determine the content type.
        Returns:
            Dict containing the clipboard content or error information
        '''
        pass

    def read_and_process_paste(self) -> Dict[str, Any]:
        '''
        Read clipboard content and if it's an image or binary file, create a temporary file
        and return a file command that can be processed.
        Returns:
            Dict containing either processed file command or regular text content
        '''
        pass

    def cleanup_temp_files(self):
        '''Clean up any temporary files created by this service.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Write content to the clipboard.
        Args:
            content: Content to write to clipboard
        Returns:
            Dict containing success status and any error information
        '''
        pass

    def __del__(self):
        '''Cleanup temporary files when the service is destroyed.'''
        pass
```

**Rewrite**

```python

class ClipboardService:
    '''Provides functionality to interact with the operating system's clipboard.'''

    def __init__(self):
        '''Sets up the clipboard service instance.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Stores the specified text in the system clipboard.
        Args:
            content: The string value to place on the clipboard
        Returns:
            Dictionary with success status and error details if applicable
        '''
        pass

    def _create_temp_file_from_image(self, image: Image.Image) -> Optional[str]:
        '''
        Converts a PIL Image object into a temporary file.
        Args:
            image: Instance of PIL Image class to save
        Returns:
            File path string for the temporary file, or None on failure
        '''
        pass

    def read(self) -> Dict[str, Any]:
        '''
        Retrieves clipboard contents and infers the data format automatically.
        Returns:
            Dictionary containing clipboard data or error information
        '''
        pass

    def read_and_process_paste(self) -> Dict[str, Any]:
        '''
        Reads clipboard data and generates a temporary file if it contains images or binaries, returning a processable file command.
        Returns:
            Dictionary with either temporary file command or raw text content
        '''
        pass

    def cleanup_temp_files(self):
        '''Deletes temporary files created by this service.'''
        pass

    def write_text(self, content: str) -> Dict[str, Any]:
        '''
        Writes the provided content to the system clipboard.
        Args:
            content: Data to be copied to clipboard
        Returns:
            Dictionary indicating operation success and error details
        '''
        pass

    def __del__(self):
        '''Removes temporary files when the service instance is destroyed.'''
        pass
```

_judge: EQUIVALENT — The rewritten specification clarifies terminology (e.g., "string value" vs "text content", "deletes" vs "clean up") without altering the core requirements, types, or behavior described in the original._

---

## 71. RealClassEval/csn/snippet_129 — `llm_terse_01` (terse)

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
        '''Fenwick tree node: single parent multiple children
        '''
        pass

    def get_ancestors(self):
        '''Ancestors list ordered earliest
        :return: node ancestors ordered most recent
        :rtype: list(FenwickNode)
        '''
        pass
```

_judge: EQUIVALENT — The rewrite maintains the core requirements (single parent and multiple children for __init__; ambiguous ancestor ordering for get_ancestors) without altering parameter types, return types, or behavioral constraints._

---

## 72. RealClassEval/post_cut-off/snippet_52 — `llm_formal_01` (formal)

**Original**

```python

class PSDConeProjection:
    '''
    Initial implementation of psd_cone_projection task.
    This will be evolved by OpenEvolve to improve performance and correctness.
    '''

    def __init__(self):
        '''Initialize the PSDConeProjection.'''
        pass

    def solve(self, problem):
        '''
        Solve the psd_cone_projection problem.
        Args:
            problem: Dictionary containing problem data specific to psd_cone_projection
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

class PSDConeProjection:
    '''
    An initial implementation of the psd_cone_projection task is provided by this class. The implementation is anticipated to be superseded by a version generated by OpenEvolve for enhanced performance and correctness.
    '''

    def __init__(self):
        '''The PSDConeProjection instance is initialized by this method.'''
        pass

    def solve(self, problem):
        '''
        The psd_cone_projection problem is solved by this method when a dictionary containing problem-specific data for the task is provided. The solution is returned in the format expected by the task.
        '''
        pass

    def is_solution(self, problem, solution):
        '''
        The validity of a proposed solution for the psd_cone_projection problem is verified by this method when the original problem instance and the proposed solution are provided. The method returns True if the solution satisfies the problem constraints, and False otherwise.
        '''
        pass
```

_judge: EQUIVALENT — The rewritten docstrings describe identical requirements, arguments, return values, and behavior as the original, differing only in phrasing and tone without altering any technical specifications._
