# This file is part of QuTiP: Quantum Toolbox in Python.
#
#    Copyright (c) 2011 and later, Paul D. Nation and Robert J. Johansson.
#    All rights reserved.
#
#    Redistribution and use in source and binary forms, with or without
#    modification, are permitted provided that the following conditions are
#    met:
#
#    1. Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#    3. Neither the name of the QuTiP: Quantum Toolbox in Python nor the names
#       of its contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
#    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#    "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
#    PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#    HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#    SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#    LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#    DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#    THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#    OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################
"""
Internal use module for manipulating dims specifications.
"""

__all__ = [] # Everything should be explicitly imported, not made available
             # by default.

import numpy as np
from operator import getitem
from functools import partial


def type_from_dims(dims, enforce_square=True):
    if   (np.prod(dims[0]) == 1 and
          isinstance(dims[1], list) and
          isinstance(dims[1][0], (int, np.integer))):
            return 'bra'
    elif (np.prod(dims[1]) == 1 and
          isinstance(dims[0], list) and
          isinstance(dims[0][0], (int, np.integer))):
            return 'ket'
    elif (np.prod(dims[0]) == 1 and
          isinstance(dims[1], list) and
          isinstance(dims[1][0], list)):
            return 'operator-bra'
    elif (np.prod(dims[1]) == 1 and
          isinstance(dims[0], list) and
          isinstance(dims[0][0], list)):
            return 'operator-ket'
    elif (isinstance(dims[0], list) and
          isinstance(dims[0][0], (int, np.integer)) and
          (dims[0] == dims[1] or not enforce_square)):
            return 'oper'
    elif (isinstance(dims[0], list) and
          isinstance(dims[0][0], list) and
          ((dims[0] == dims[1] and
            dims[0][0] == dims[1][0])
           or not enforce_square)
          ):
            return 'super'
    else:
            return 'other'


def flatten(l):
    """Flattens a list of lists to the first level.

    Given a list containing a mix of scalars and lists,
    flattens down to a list of the scalars within the original
    list.

    Examples
    --------

    >>> print(flatten([[[0], 1], 2]))
    [0, 1, 2]

    """
    if not isinstance(l, list):
        return [l]
    else:
        return sum(map(flatten, l), [])


def deep_remove(l, *what):
    """Removes scalars from all levels of a nested list.

    Given a list containing a mix of scalars and lists,
    returns a list of the same structure, but where one or
    more scalars have been removed.

    Examples
    --------

    >>> print(deep_remove([[[[0, 1, 2]], [3, 4], [5], [6, 7]]], 0, 5))
    [[[[1, 2]], [3, 4], [], [6, 7]]]

    """
    if isinstance(l, list):
        # Make a shallow copy at this level.
        l = l[:]
        for to_remove in what:
            if to_remove in l:
                l.remove(to_remove)
            else:
                l = list(map(lambda elem: deep_remove(elem, to_remove), l))
    return l


def unflatten(l, idxs):
    """Unflattens a list by a given structure.

    Given a list of scalars and a deep list of indices
    as produced by `flatten`, returns an "unflattened"
    form of the list. This perfectly inverts `flatten`.

    Examples
    --------

    >>> l = [[[10, 20, 30], [40, 50, 60]], [[70, 80, 90], [100, 110, 120]]]
    >>> idxs = enumerate_flat(l)
    >>> print(unflatten(flatten(l)), idxs) == l
    True

    """
    acc = []
    for idx in idxs:
        if isinstance(idx, list):
            acc.append(unflatten(l, idx))
        else:
            acc.append(l[idx])
    return acc


def _enumerate_flat(l, idx=0):
    if not isinstance(l, list):
        # Found a scalar, so return and increment.
        return idx, idx + 1
    else:
        # Found a list, so append all the scalars
        # from it and recurse to keep the increment
        # correct.
        acc = []
        for elem in l:
            labels, idx = _enumerate_flat(elem, idx)
            acc.append(labels)
        return acc, idx


def enumerate_flat(l):
    """Labels the indices at which scalars occur in a flattened list.

    Given a list containing a mix of scalars and lists,
    returns a list of the same structure, where each scalar
    has been replaced by an index into the flattened list.

    Examples
    --------

    >>> print(enumerate_flat([[[10], [20, 30]], 40]))
    [[[0], [1, 2]], 3]

    """
    return _enumerate_flat(l)[0]


def deep_map(fn, collection, over=(tuple, list)):
    if isinstance(collection, over):
        return type(collection)(deep_map(fn, el, over) for el in collection)
    else:
        return fn(collection)


def dims_to_tensor_perm(dims):
    """
    Given the dims of a Qobj instance, returns a list representing
    a permutation from the flattening of that dims specification to
    the corresponding tensor indices.

    Parameters
    ----------

    dims : list
        Dimensions specification for a Qobj.

    Returns
    -------

    perm : list
        A list such that ``data[flatten(dims)[idx]]`` gives the
        index of the tensor ``data`` corresponding to the ``idx``th
        dimension of ``dims``.
    """
    # We figure out the type of the dims specification,
    # relaxing the requirement that operators be square.
    # This means that dims_type need not coincide with
    # Qobj.type, but that works fine for our purposes here.
    dims_type = type_from_dims(dims, enforce_square=False)
    perm = enumerate_flat(dims)

    # If type is oper, ket or bra, we don't need to do anything.
    if dims_type in ('oper', 'ket', 'bra'):
        return flatten(perm)

    # If the type is other, we need to figure out if the
    # dims is superlike on its outputs and inputs
    # This is the case if the dims type for left or right
    # are, respectively, oper-like.
    if dims_type == 'other':
        raise NotImplementedError("Not yet implemented for type='other'.")

    # If we're still here, the story is more complicated. We'll
    # follow the strategy of creating a permutation by using
    # enumerate_flat then transforming the result to swap
    # input and output indices of vectorized matrices, then flattening
    # the result. We'll then rebuild indices using this permutation.


    if dims_type in ('operator-ket', 'super'):
        # Swap the input and output spaces of the right part of
        # perm.
        perm[1] = list(reversed(perm[1]))

    if dims_type in ('operator-bra', 'super'):
        # Ditto, but for the left indices.
        perm[0] = list(reversed(perm[0]))

    return flatten(perm)

def dims_to_tensor_shape(dims):
    """
    Given the dims of a Qobj instance, returns the shape of the
    corresponding tensor. This helps, for instance, resolve the
    column-stacking convention for superoperators.

    Parameters
    ----------

    dims : list
        Dimensions specification for a Qobj.

    Returns
    -------

    tensor_shape : tuple
        NumPy shape of the corresponding tensor.
    """

    perm = dims_to_tensor_perm(dims)
    dims = flatten(dims)

    return tuple(map(partial(getitem, dims), perm))


def dims_idxs_to_tensor_idxs(dims, indices):
    """
    Given the dims of a Qobj instance, and some indices into
    dims, returns the corresponding tensor indices. This helps
    resolve, for instance, that column-stacking for superoperators,
    oper-ket and oper-bra implies that the input and output tensor
    indices are reversed from their order in dims.

    Parameters
    ----------

    dims : list
        Dimensions specification for a Qobj.

    indices : int, list or tuple
        Indices to convert to tensor indices. Can be specified
        as a single index, or as a collection of indices.
        In the latter case, this can be nested arbitrarily
        deep. For instance, [0, [0, (2, 3)]].

    Returns
    -------

    tens_indices : int, list or tuple
        Container of the same structure as indices containing
        the tensor indices for each element of indices.
    """

    perm = dims_to_tensor_perm(dims)
    return deep_map(partial(getitem, perm), indices)
