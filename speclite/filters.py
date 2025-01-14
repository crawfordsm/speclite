# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Support for calculations involving filter response curves.

Overview
--------

See :doc:`/filters` for information about the standard filters included with
this code distribution and instructions for adding your own filters. Filter
names have two components, a group name and a band name, which are combined
with a hyphen, e.g. "sdss2010-r".  The group names included with this package
are:

    >>> filter_group_names
    ['sdss2010', 'decam2014', 'wise2010', 'bessell']

List the band names associated with any group using, for example:

    >>> load_filters('sdss2010-*').names
    ['sdss2010-u', 'sdss2010-g', 'sdss2010-r', 'sdss2010-i', 'sdss2010-z']

Here is a brief example of calculating SDSS r,i and Bessell V magnitudes for a
numpy array of fluxes for 100 spectra covering 4000-10,000 A with 1A pixels:

    >>> import astropy.units as u
    >>> wlen = np.arange(4000, 10000) * u.Angstrom
    >>> flux = np.ones((100, len(wlen))) * u.erg / (u.cm**2 * u.s * u.Angstrom)

Units are recommended but not required (otherwise, the units shown here are
assumed as defaults).  Next, load the filter responses:

    >>> import speclite.filters
    >>> filters = speclite.filters.load_filters(
    ...     'sdss2010-r', 'sdss2010-i', 'bessell-V')

Finally, calculate the magnitudes to obtain an :class:`astropy Table
<astropy.table.Table>` of results with one row per input spectrum and one
column per filter:

    >>> mags = filters.get_ab_magnitudes(flux, wlen)

.. _convolution-operator:

Convolutions
------------

The filter response convolution operator implemented here is defined as:

.. math::

    F[R,f] \equiv \int_0^\infty \\frac{dg}{d\lambda}(\lambda)
    R(\lambda) \omega(\lambda) d\lambda

where :math:`R(\lambda)` is a filter response function, represented by a
:class:`FilterResponse` object, and :math:`dg/d\lambda` is an arbitrary
differential function of wavelength, which can either be represented as a
callable python object or else with arrays of wavelengths and function values.

.. _weights:

The default weights:

.. math::

    \omega(\lambda) = \\frac{\lambda}{h c}

are appropriate for photon-counting detectors such as CCDs, and enabled by
the default setting ``photon_weighted = True`` in the methods below.  Otherwise,
the convolution is unweighted, :math:`\omega(\lambda) = 1`, but arbitrary
alternative weights can always be included in the definition of
:math:`f(\lambda)`. For example, a differential function of frequency
:math:`dg/d\\nu` can be reweighted using:

.. math::

    \\frac{dg}{d\lambda}(\lambda) =
    \\frac{c}{\lambda^2} \\frac{dg}{d\\nu}(\\nu = c/\lambda)

These defintions make no assumptions about the units of
:math:`dg/d\lambda`, but magnitude calculations are an important special case
where the units of :math:`f_\lambda = dg/d\lambda` must have the dimensions
:math:`M / (L T^3)`, for example,
:math:`\\text{erg}/(\\text{cm}^2\,\\text{s}\,\AA)`.

.. _magnitude:

The magnitude of :math:`f_\lambda` in the filter band with response
:math:`R` is then:

.. math::

    m[R,f_\lambda] \equiv -2.5 \log_{10}(F[R,f_\lambda] / F[R,f_{\lambda,0}])

where :math:`f_{\lambda,0}(\lambda)` is the reference flux density that defines
the photometric system's zeropoint :math:`F[R,f_{\lambda,0}]`.  The zeropoint
has dimensions :math:`1 / (L^2 T)` and gives the rate of incident photons
per unit telescope area from a zero magnitude source.

A spectral flux density per unit frequency, :math:`f_\\nu = dg/d\\nu`, should be
converted using:

.. math::

    f_\lambda(\lambda) = \\frac{c}{\lambda^2} f_\\nu(\\nu = c/\lambda)

for use with the methods implemented here.

For the AB system,

.. math::

    f_{\lambda,0}^{AB}(\lambda) = \\frac{c}{\lambda^2} (3631 \\text{Jy}) \; ,

and the convolutions use photon-counting weights.

.. _sampling:

Sampling
--------

Filter responses are tabulated on non-uniform grids with sufficient sampling
that linear interpolation is sufficient for most applications. When a filter
response is convolved with tabulated data, we must also consider the sampling
of the tabulated function. In this implementation, we assume that the tabulated
function is also sufficiently sampled to allow linear interpolation.

The next issue is how to sample the product of a filter response and tabulated
function when performing a numerical convolution integral.  With the assumptions
above, a safe strategy would be to sample the integrand at the union of the
two wavelength grids.  However, this is relatively expensive since it requires
interpolating both the response and the input function. Interpolation is
sometimes unavoidable: for example, when the function is linear and represented
by its values at only two wavelengths.

The approach adopted here is to use the sampling grid of the input function
to sample the convolution integrand whenever it samples the filter response
sufficiently.  This requires that the filter response be interpolated, but this
operation only needs to be performed once when many convolutions are performed
on the same input wavelength grid.  Our criteria for sufficient filter sampling
is that at most one filter wavelength point lies between any consecutive pair
of input wavelength points.  When this condition is not met, the input
function will be interpolated at the minimum number of response wavelengths
necesssary to satisfy the condition.

The figure below (generated by :func:`this function
<filter_sampling_explanatory_plot>`) illustrates three different sampling
regimes that can occur
in a convolution with the Bessell V filter (red curve). Filled blue squares
show where the input function is sampled and open blue circles show where
interpolation of the input function is performed.  The left-hand plot shows
an extremely undersampled input that is interpolated at every filter point.
The middle plot shows a well sampled input that requires no interpolation.
The right-hand plot shows an input that is slightly undersampled and requires
interpolation at some of the filter points. All three methods give consistent
results, with discrepancies of < 0.05%.

.. image:: _static/sampling.png
    :alt: sampling explanatory plot

The logic described here is encapsulated in the :class:`FilterConvolution`
class.  Interpolation is performed automatically, as necessary, by the
high-level magnitude calculating methods, but :class:`FilterConvolution` is
available when more control of this process is needed to improve performance.

.. _performance:

Performance
-----------

If the performance of magnitude calculations is a bottleneck, you can
speed up the code significantly by taking advantage of the fact that all
of the convolution functions can operate on multidimensional arrays.  For
example, calling :meth:`FilterResponse.get_ab_magnitudes` once with an
array of 5000 spectra is about 10x faster than calling it 5000 times with the
individual spectra.  However, in order to take advantage of this speedup,
your spectra need to all use the same wavelength grid.

Note that the eliminating flux units (which are always optional) from your
input spectra will only result in about a 10% speedup, so units are generally
recommended.

Attributes
----------
filter_group_names : list
    List of filter group names included with this package.
default_wavelength_unit : :class:`astropy.units.Unit`
    The default wavelength units assumed when units are not specified.
    The same units are used to store wavelength values in internal arrays.
default_flux_unit : :class:`astropy.units.Unit`
    The default units for spectral flux density per unit wavelength.
"""
from __future__ import print_function, division

import os
import os.path
import glob
import re
import collections

import numpy as np

import scipy.interpolate
import scipy.integrate

import astropy.table
import astropy.units
import astropy.utils.data


filter_group_names = [
    'sdss2010', 'decam2014', 'wise2010', 'bessell']

default_wavelength_unit = astropy.units.Angstrom

default_flux_unit = (astropy.units.erg / astropy.units.cm**2 /
                     astropy.units.s / default_wavelength_unit)

# Constant spectral flux density per unit frequency for a zero magnitude
# AB source.
_ab_constant = (
    3631. * astropy.units.Jansky * astropy.constants.c).to(
        default_flux_unit * default_wavelength_unit**2)

# The units specified below give AB zeropoints in 1 / (cm**2 s).
_hc_constant = (astropy.constants.h * astropy.constants.c).to(
    astropy.units.erg * default_wavelength_unit)

_photon_weighted_unit = default_wavelength_unit**2 / _hc_constant.unit

# Map names to integration methods allowed by the convolution methods below.
_filter_integration_methods = dict(
    trapz= scipy.integrate.trapz,
    simps= scipy.integrate.simps)

# Group and band names must be valid python identifiers. Although a leading
# underscore is probably not a good idea, it is simpler to stick with a
# well-established lexical class.
# https://docs.python.org/2/reference/lexical_analysis.html#identifiers
_name_pattern = re.compile('^[a-zA-Z_][a-zA-Z0-9_]*\Z')

# The wildcard pattern is "<group_name>-*" and captures <group_name>.
_group_wildcard = re.compile('^([a-zA-Z_][a-zA-Z0-9_]*)-\*\Z')

# Dictionary of cached FilterResponse objects.
_filter_cache = {}


def ab_reference_flux(wavelength, magnitude=0.):
    """Calculate an AB reference spectrum with the specified magnitude.

    For example, to calculate the flux of a 20th magnitude AB reference
    at 600 nm:

    >>> flux = ab_reference_flux(600 * astropy.units.nanometer, magnitude=20)
    >>> print('{0:.3g}'.format(flux))
    3.02e-17 erg / (Angstrom cm2 s)

    This function is used to calculate :attr:`filter response zeropoints
    <FilterResponse.ab_zeropoint>` in the AB system.

    If either of the parameters is an array, the result will be broadcast
    over the parameters using the usual numpy rules.

    Parameters
    ----------
    wavelength : astropy.units.Quantity
        Wavelength or array of wavelengths where the flux should be
        evaluated.  Wavelengths must have valid units.
    magnitude : float or array
        Dimensionless magnitude value(s) used to normalize the spectrum.

    Returns
    -------
    astropy.units.Quantity
        Spectral flux densities per unit wavelength tabulated at each input
        wavelength, in units of :attr:`default_flux_unit`.

    Raises
    ------
    ValueError
        Wavelength parameter does not have valid units.
    """
    magnitude = np.asarray(magnitude)
    try:
        wavelength = wavelength.to(default_wavelength_unit)
    except (AttributeError, astropy.units.UnitConversionError):
        raise ValueError('Cannot evaluate flux for invalid wavelength.')

    flux = 10 ** (-0.4 * magnitude) * _ab_constant / wavelength ** 2
    return flux.to(default_flux_unit)


def validate_wavelength_array(wavelength, min_length=0):
    """Validate a wavelength array for filter operations.

    This function will not perform any copying or allocation if the input
    is already a numpy array or astropy Quantity.

    Parameters
    ----------
    wavelength : array
        A 1D array of strictly increasing wavelength values with optional
        units.  If units are included, they must be convertible to
        :attr:`default_wavelength_unit`.  Otherwise, the
        :attr:`default_wavelength_unit` is assumed.
    min_length : int
        The minimum required length of the wavelength array.

    Returns
    -------
    numpy.ndarray
        Array of validated wavelengths without any units, but with values
        given in :attr:`default_wavelength_unit`.

    Raises
    ------
    ValueError
        Wavelength array is not 1D, or not strictly increasing, or below
        the minimum length.
    astropy.units.UnitConversionError
        The wavelength array has units that are not convertible to
        :attr:`default_wavelength_unit`
    """
    wavelength_no_units = np.asarray(wavelength)
    try:
        wavelength_no_units *= wavelength.unit.to(default_wavelength_unit)
    except AttributeError:
        # No units present, so assume default units.
        pass
    if len(wavelength_no_units.shape) != 1:
        raise ValueError('Wavelength array must be 1D.')
    if len(wavelength_no_units) < min_length:
        raise ValueError('Minimum length is {0}.'.format(min_length))
    if not np.all(np.diff(wavelength_no_units) > 0):
        raise ValueError('Wavelength values must be strictly increasing.')
    return wavelength_no_units


def tabulate_function_of_wavelength(function, wavelength, verbose=False):
    """Evaluate a function of wavelength.

    Parameters
    ----------
    function : callable
        Any function that expects a wavelength or array of wavelengths and
        returns its value.  Functions will be called first with wavelength
        units included and then without units included, in which case they
        should treat all wavelengths as having
        :attr:`default_wavelength_unit`. If a function returns a value with
        units, this will be correctly propagated to the output.
    wavelength : astropy.units.Quantity
        Wavelength or array of wavelengths where the function should be
        evaluated.  Wavelengths must have valid units.
    verbose : bool
        Print details of the sequence of attempts used to call the function.

    Returns
    -------
    tuple
        Tuple (values, units) of function values at each input wavelength.
    """
    try:
        wavelength = wavelength.to(default_wavelength_unit)
    except (AttributeError, astropy.units.UnitConversionError):
        raise ValueError('Cannot evaluate function for invalid wavelength.')

    function_units = None
    # Try broadcasting our wavelength array with its units.
    if verbose:
        print('Trying to broadcast with units.')
    try:
        function_values = function(wavelength)
        try:
            function_units = function_values.unit
            function_values = function_values.value
        except AttributeError:
            # Ok if the function does not return any units.
            pass
        return function_values, function_units
    except Exception as e:
        # Keep trying.
        if verbose:
            print('Failed: {0}'.format(e))
    # Try broadcasting our wavelength array without its units.
    if verbose:
        print('Trying to broadcast without units.')
    try:
        function_values = function(wavelength.value)
        try:
            function_units = function_values.unit
            function_values = function_values.value
        except AttributeError:
            # Ok if the function does not return any units.
            pass
        return function_values, function_units
    except Exception as e:
        # Keep trying.
        if verbose:
            print('Failed: {0}'.format(e))
    # Try looping over wavelengths and including units.
    if verbose:
        print('Trying to iterate with units.')
    try:
        function_values = []
        for i, w in enumerate(wavelength.value):
            value = function(w * default_wavelength_unit)
            # Check that the function is consistent in the units it returns.
            if i == 0:
                # Remember the units of the first function value.
                try:
                    function_units = value.unit
                    value = value.value
                except AttributeError:
                    # Ok if the function does not return any units.
                    pass
            elif function_units == None:
                try:
                    new_units = value.unit
                    # Function has units now but did not earlier.
                    raise RuntimeError(
                        'Inconsistent function units: none, {0}.'
                        .format(new_units))
                except AttributeError:
                    # Still no units, as expected.
                    pass
            else:
                try:
                    if function_units != value.unit:
                        # Function units have changed.
                        raise RuntimeError(
                            'Inconsistent function units: {0}, {1}.'
                            .format(function_units, value.unit))
                except AttributeError:
                    # Function had units before but does not now.
                    raise RuntimeError(
                        'Inconsistent function units: {0}, none.'
                        .format(function_units))
                value = value.value

            function_values.append(value)
        function_values = np.asarray(function_values)
        return function_values, function_units
    except RuntimeError as e:
        raise e
    except Exception as e:
        # Keep trying.
        if verbose:
            print('Failed: {0}'.format(e))
    # Try looping over wavelengths and not including units.
    if verbose:
        print('Trying to iterate without units.')
    try:
        function_values = []
        for i, w in enumerate(wavelength.value):
            value = function(w)
            # Check that the function is consistent in the units it returns.
            if i == 0:
                # Remember the units of the first function value.
                try:
                    function_units = value.unit
                    value = value.value
                except AttributeError:
                    # Ok if the function does not return any units.
                    pass
            elif function_units == None:
                try:
                    new_units = value.unit
                    # Function has units now but did not earlier.
                    raise RuntimeError(
                        'Inconsistent function units: none, {0}.'
                        .format(new_units))
                except AttributeError:
                    # Still no units, as expected.
                    pass
            else:
                try:
                    if function_units != value.unit:
                        # Function units have changed.
                        raise RuntimeError(
                            'Inconsistent function units: {0}, {1}.'
                            .format(function_units, value.unit))
                except AttributeError:
                    # Function had units before but does not now.
                    raise RuntimeError(
                        'Inconsistent function units: {0}, none.'
                        .format(function_units))
                value = value.value

            function_values.append(value)
        function_values = np.asarray(function_values)
        return function_values, function_units
    except RuntimeError as e:
        raise e
    except Exception as e:
        if verbose:
            print('Failed: {0}'.format(e))
        # If we get here, none of the above strategies worked.
        raise ValueError('Invalid function.')


class FilterResponse(object):
    """A filter response curve tabulated in wavelength.

    Some standard filters are included in this package and can be initialized
    using :func:`load_filter`.  For example:

    >>> rband = load_filter('sdss2010-r')

    Objects behave like functions that evaluate their response at aribtrary
    wavelengths.  Wavelength units can be specified, or else default to
    :attr:`default_wavelength_unit`:

    >>> round(rband(6000 * astropy.units.Angstrom), 4)
    0.5323
    >>> round(rband(6000), 4)
    0.5323
    >>> round(rband(0.6 * astropy.units.micron), 4)
    0.5323

    Filters can be also evaluated for an arbitrary array of wavelengths,
    returning a numpy array of response values:

    >>> np.round(rband([5980, 6000, 6020]), 4)
    array([ 0.5309,  0.5323,  0.5336])

    The effective wavelength of a filter is defined as the
    :ref:`photon-weighted <weights>` mean wavelength:

    .. math::

        \lambda_{eff} \equiv F[R, \lambda] / F[R, 1]

    where :math:`F` is our convolution operator defined :ref:`above
    <convolution-operator>`.  Use the :attr:`effective_wavelength` attribute to
    access this value:

    >>> print(np.round(rband.effective_wavelength, 1))
    6197.7 Angstrom

    The examples below show three different ways to calculate the AB magnitude
    in the ``sdss2010-r`` filter for a source with a constant spectral flux
    density per unit wavelength of
    :math:`10^{-17} \\text{erg}/(\\text{cm}^2\, \\text{s} \,\AA)`.  First, we
    specify the spectrum with a function object:

    >>> flux = lambda wlen: 1e-17 * default_flux_unit
    >>> print(rband.get_ab_magnitude(flux).round(3))
    21.141

    Next, we tabulate a constant flux using only two wavelength points that
    span the filter response:

    >>> wlen = [5300, 7200] * default_wavelength_unit
    >>> flux = [1e-17, 1e-17] * default_flux_unit
    >>> print(rband.get_ab_magnitude(flux, wlen).round(3))
    21.141

    Since this spectrum undersamples the filter response, it is automatically
    interpolated.  Finally, we tabulate a constant flux using a dense
    wavelength grid that oversamples the filter response and does not require
    any interpolation:

    >>> wlen = np.linspace(5300, 7200, 200) * default_wavelength_unit
    >>> flux = np.ones_like(wlen.value) * 1e-17 * default_flux_unit
    >>> print(rband.get_ab_magnitude(flux, wlen).round(3))
    21.141

    Parameters
    ----------
    wavelength : array
        A :func:`valid array <validate_wavelength_array>` of wavelengths.
    response : array
        A dimensionless 1D array of filter response values corresponding to
        each wavelength.  Response values must be non-negative and cannot all
        be zero. The bounding response values must be zero, and the response
        is assumed to be zero outside of the specified wavelength range. If
        this parameter has units, they will be silently ignored.
    meta : dict
        A dictionary of metadata which must include values for the keys
        ``group_name`` and ``band_name``, which must be `valid python
        identifiers
        <https://docs.python.org/2/reference/lexical_analysis.html#identifiers>`__.
        However, you are encouraged to provide the full set of keys listed
        :doc:`here </filters>`, and additional keys are also permitted.

    Attributes
    ----------
    name : str
        Canonical name of this filter response in the format
        "<group_name>-<band_name>".
    effective_wavelength : :class:`astropy.units.Quantity`
        Mean :ref:`photon-weighted <weights>` wavelength of this response
        function, as defined above.
    ab_zeropoint : :class:`astropy.units.Quantity`
        Zeropoint for this filter response in the AB system, as defined
        :ref:`above <magnitude>`, and including units.
    response : numpy.ndarray
        Numpy array of response values passed to our constructor, after
        trimming any extra leading or trailing zero response values.
    meta : dict
        Dictionary of metadata associated with this filter.
    interpolator : :class:`scipy.interpolate.interp1d`
        Linear interpolator of our response function that returns zero for
        all values outside our wavelength range.  Should normally be evaluated
        through our :meth:`__call__` convenience method.

    Raises
    ------
    ValueError
        Invalid wavelength or response input arrays, or missing required keys
        in the input metadata.
    """
    def __init__(self, wavelength, response, meta):

        self._wavelength = validate_wavelength_array(wavelength, min_length=3)
        # If response has units, np.asarray() makes a copy and drops the units.
        self.response = np.asarray(response)
        if len(self._wavelength) != len(self.response):
            raise ValueError('Arrays must have same length.')

        # Check for a valid response curve.
        if np.any(self.response < 0):
            raise ValueError('Response values must be non-negative.')
        if np.all(self.response == 0):
            raise ValueError('Response values cannot all be zero.')
        if not (self.response[0] == 0 and self.response[-1] == 0):
            raise ValueError('Response must go to zero on both sides.')

        # Trim any extra leading and trailing zeros.
        non_zero = np.where(self.response > 0)[0]
        start, stop = non_zero[0] - 1, non_zero[-1] + 2
        if stop - start < len(self._wavelength):
            self._wavelength = self._wavelength[start: stop]
            self.response = self.response[start: stop]

        # Check for the required metadata fields.
        try:
            self.meta = dict(meta)
        except TypeError:
            raise ValueError('Invalid metadata dictionary.')
        for required in ('group_name', 'band_name'):
            if required not in self.meta:
                raise ValueError(
                    'Metadata missing required key "{0}".'.format(required))
            try:
                if not _name_pattern.match(meta[required]):
                    raise ValueError(
                        'Value of {0} is not a valid identifier: "{1}"'
                        .format(required, meta[required]))
            except TypeError:
                raise ValueError('Invalid value type for {0}.'.format(required))

        # Create a linear interpolator of our response function that returns
        # zero outside of our wavelength range.
        self.interpolator = scipy.interpolate.interp1d(
            self._wavelength, self.response, kind='linear',
            copy=False, assume_sorted=True,
            bounds_error=False, fill_value=0.)

        # Calculate this filter's effective wavelength.
        one = astropy.units.Quantity(1.)
        numer = self.convolve_with_function(lambda wlen: wlen)
        denom = self.convolve_with_function(lambda wlen: one)
        self.effective_wavelength = numer / denom

        # Calculate this filter's zeropoint in the AB system.
        self.ab_zeropoint = self.convolve_with_function(
            ab_reference_flux, units=default_flux_unit)

        # Remember this object in our cache so that load_filter can find it.
        # In case this object is already in our cache, overwrite it now.
        self.name = '{0}-{1}'.format(meta['group_name'], meta['band_name'])
        _filter_cache[self.name] = self


    def __call__(self, wavelength):
        """Evaluate the filter response at arbitrary wavelengths.

        Parameters
        ----------
        wavelength : array or float
            A single wavelength value or an array of wavelengths.
            If units are included, they will be correctly interpreted.
            Otherwise :attr:`default_wavelength_unit` is assumed.

        Returns
        -------
        numpy.ndarray
            Numpy array of response values corresponding to each input
            wavelength.

        Raises
        ------
        astropy.units.UnitConversionError
            Input wavelength(s) have unit that is not convertible to
            :attr:`default_wavelength_unit`.
        """
        # Use asanyarray() so that a Quantity with units is not copied here.
        wavelength = np.asanyarray(wavelength)
        try:
            wavelength = wavelength.to(default_wavelength_unit).value
        except AttributeError:
            # No units present, so assume the default units.
            pass
        response = self.interpolator(wavelength)
        # If the input was scalar, return a scalar.
        if response.shape == ():
            response = np.asscalar(response)
        return response


    def save(self, directory_name='.'):
        """Save this filter response to file.

        The response is saved in the `ECSV format
        <https://github.com/astropy/astropy-APEs/blob/master/APE6.rst>`__
        and can be read back by passing the returned path to
        :func:`load_filter`::

            file_name = response.save()
            response2 = load_filter(file_name)

        The file name in the specified directory will be
        "<group_name>-<band_name>.ecsv". Any existing file with the same name
        will be silently overwritten.

        Parameters
        ----------
        directory_name : str
            An existing directory where the response file should be written.

        Returns
        -------
        str
            Absolute path of the created file, including the .ecsv extension.

        Raises
        ------
        ValueError
            Directory name does not exist or refers to a file.
        """
        if not os.path.isdir(directory_name):
            raise ValueError('Invalid directory name.')
        table = astropy.table.QTable(meta=self.meta)
        table['wavelength'] = self._wavelength * default_wavelength_unit
        table['response'] = self.response
        name = os.path.join(
            directory_name,
            '{0}-{1}.ecsv'.format(
                self.meta['group_name'], self.meta['band_name']))
        table.write(name, format='ascii.ecsv')
        return os.path.abspath(name)


    def convolve_with_function(self, function, photon_weighted=True,
                               units=None, method='trapz'):
        """Convolve this response with a function of wavelength.

        Returns a numerical estimate of the convolution integral :math:`F[R,f]`
        defined above for an arbitrary function of wavelength
        :math:`f(\lambda)`.  For example, to calculate a filter's
        effective wavelength:

        >>> rband = load_filter('sdss2010-r')
        >>> one = astropy.units.Quantity(1.)
        >>> numer = rband.convolve_with_function(lambda wlen: wlen)
        >>> denom = rband.convolve_with_function(lambda wlen: one)
        >>> print(np.round(numer / denom, 1))
        6197.7 Angstrom

        Similarly, a filter's zeropoint can be calculated using:

        >>> zpt = rband.convolve_with_function(ab_reference_flux)
        >>> print(zpt.round(1))
        551725.0 1 / (cm2 s)

        Note that both of these values are pre-calculated in the constructor and
        are available from the :attr:`effective_wavelength` and
        :attr:`ab_zeropoint` attributes.

        Parameters
        ----------
        function : callable
            Any function that expects a wavelength or array of wavelengths and
            returns its value.  Functions will be called first with wavelength
            units included and then without units included, in which case they
            should treat all wavelengths as having
            :attr:`default_wavelength_unit`. If a function returns a value with
            units, this will be correctly propagated to the convolution result.
        photon_weighted : bool
            Use :ref:`weights <weights>` appropriate for a photon-counting
            detector such as a CCD when this parameter is True.  Otherwise,
            use unit weights.
        units : astropy.units.Quantity or None
            When this parameter is not None, then any explicit units returned
            by the function must be convertible to these units, and these units
            will be applied if the function values do not already have units.
        method : str
            Specifies the numerical integration scheme to use and must be either
            'trapz' or 'simps', to select the corresponding
            ``scipy.integration`` function. The 'simps' method may be more
            accurate than the default 'trapz' method, but should be used with
            care since it is also less robust and more sensitive to the
            wavelength grid.

        Returns
        -------
        float or astropy.units.Quantity
            Result of the convolution integral.  Units will be included if the
            function returns a value with units.  Otherwise, the implicit units
            of the result are equal to the implicit function value units
            multiplied by :attr:`default_wavelength_unit`.

        Raises
        ------
        ValueError
            Function does not behave as expected or invalid method.
        RuntimeError
            Function returns inconsistent units.
        """
        if method not in _filter_integration_methods.keys():
            raise ValueError(
                'Invalid integration method {0}. Pick one of {1}.'
                .format(method, _filter_integration_methods.keys()))

        # Try to tabulate the function to integrate on our wavelength grid.
        integrand, func_units = \
            tabulate_function_of_wavelength(
                function, self._wavelength * default_wavelength_unit)
        if units is not None:
            if func_units is not None:
                try:
                    converted = func_units.to(units)
                except astropy.units.UnitConversionError:
                    raise ValueError(
                        'Function units {0} not convertible to {1}.'
                        .format(func_units, units))
            else:
                func_units = units
        # Build the integrand by including appropriate weights.
        integrand *= self.response
        if photon_weighted:
            integrand *= self._wavelength / _hc_constant.value
            if func_units is not None:
                func_units *= default_wavelength_unit / _hc_constant.unit

        integrator = _filter_integration_methods[method]
        result = integrator(y = integrand, x=self._wavelength)

        # Apply units to the result if the fuction has units.
        if func_units is not None:
            result = result * func_units * default_wavelength_unit
        return result


    def convolve_with_array(self, wavelength, values, photon_weighted=True,
                            interpolate=False, axis=-1, units=None,
                            method='trapz'):
        """Convolve this response with a tabulated function of wavelength.

        This is a convenience method that creates a temporary
        :class:`FilterConvolution` object to perform the convolution. See
        that class' documentation for details on this method's parameters
        and usage. See also the notes :ref:`above <sampling>` about how the
        convolution integrand is sampled.

        Parameters
        ----------
        wavelength : array
            A :func:`valid array <validate_wavelength_array>` of wavelengths
            that must cover the full range of this filter's response.
        values : array or :class:`astropy.units.Quantity`
            Array of function values to use.  Values are assumed to be
            tabulated on our wavelength grid.  Values can be multidimensional,
            in which case an array of convolution results is returned. If
            values have units, then these are propagated to the result.
        photon_weighted : bool
            Use :ref:`weights <weights>` appropriate for a photon-counting
            detector such as a CCD when this parameter is True.  Otherwise, use
            unit weights.
        interpolate : bool
            Allow interpolation of the tabulated function if necessary. See
            :class:`FilterConvolution` for details.
        axis : int
            In case of multidimensional function values, this specifies the
            index of the axis corresponding to the wavelength dimension.
        units : astropy.units.Quantity or None
            When this parameter is not None, then any explicit values units
            must be convertible to these units, and these units
            will be applied to the values if they do not already have units.
        method : str
            Specifies the numerical integration scheme to use. See
            :class:`FilterConvolution` for details.

        Returns
        -------
        float or array or :class:`astropy.units.Quantity`
            Convolution integral result(s).  If the input values have units
            then these are propagated to the result(s).  If the input is
            multidimensional, then so is the result but with the specified
            axis integrated out.
        """
        convolution = FilterConvolution(
            self, wavelength, photon_weighted, interpolate, units)
        return convolution(values, axis, method)


    def get_ab_maggies(self, spectrum, wavelength=None, axis=-1):
        """Calculate a spectrum's relative AB flux convolution.

        The result is the dimensionless ratio
        :math:`F[R,f_\lambda] / F[R,f_{\lambda,0}]` defined :ref:`above
        <convolution-operator>`, and provides a linear measure of a source's
        flux through this filter relative to an AB standard flux.

        Use :meth:`get_ab_magnitude` for the corresponding AB magnitude.

        Parameters
        ----------
        spectrum : callable or array or :class:`astropy.units.Quantity`
            The spectrum whose flux should be compared with the AB standard
            flux in this filter band.  Can either be a callable object (see
            :meth:`convolve_with_function` for details) or else an array (See
            :meth:`convolve_with_array` for details). A multidimensional
            array can be used to calculate maggies for many spectra at once.
            The spectrum fluxes must either have explicit units that are
            convertible to :attr:`default_flux_unit`, or else they will be
            implicitly interpreted as having these default units.
        wavelength : array or :class:`astropy.units.Quantity` or None
            When this parameter is None, the spectrum must be a callable object.
            Otherwise, the spectrum must be an array.
        axis : int
            The axis along which wavelength increases in a spectrum array.
            Ignored when the wavelength parameter is None.

        Returns
        -------
        float or array
        """
        if wavelength is None:
            convolution = self.convolve_with_function(
                spectrum, photon_weighted=True, units=default_flux_unit)
        else:
            # Allow interpolation since this is a convenience method.
            convolution = self.convolve_with_array(
                wavelength, spectrum, photon_weighted=True,
                interpolate=True, axis=axis, units=default_flux_unit)
        try:
            return convolution.value / self.ab_zeropoint.value
        except AttributeError:
            return convolution / self.ab_zeropoint.value


    def get_ab_magnitude(self, spectrum, wavelength=None, axis=-1):
        """Calculate a spectrum's AB magnitude.

        Use :meth:`get_ab_maggies` for the corresponding dimensionless ratio
        :math:`F[R,f_\lambda] / F[R,f_{\lambda,0}]`.  The magnitude is
        calculated as:

        .. math:
            -2.5 \log_{10}(F[R,f_\lambda] / F[R,f_{\lambda,0}])

        Parameters
        ----------
        spectrum : callable or array or :class:`astropy.units.Quantity`
            See :meth:`get_ab_maggies` for details.
        wavelength : array or :class:`astropy.units.Quantity` or None
            See :meth:`get_ab_maggies` for details.
        axis : int
            See :meth:`get_ab_maggies` for details.

        Returns
        -------
        float or array
        """
        maggies = self.get_ab_maggies(spectrum, wavelength, axis)
        return -2.5 * np.log10(maggies)


class FilterConvolution(object):
    """Convolve a filter response with a tabulated function.

    See :ref:`above <convolution-operator>` for details on how the convolution
    operator implemented by this class is defined, and :ref:`here <sampling>`
    for details on how the convolution integrand is sampled.

    Most of the computation involved depends only on the tabulated function's
    wavelength grid, and not on the function values, so this class does the
    necessary initialization in its constructor, resulting in a function
    object that can be efficiently re-used with different function values.

    Use this class to efficiently perform repeated convolutions of different
    tabulated functions for the same filter on the same wavelength grid.
    When efficiency is not important or the wavelength grid changes for each
    convolution, the convencience method
    :meth:`FilterResponse.convolve_with_array` can be used instead.

    Parameters
    ----------
    response : :class:`FilterResponse` or str
        A FilterResponse object or else a fully qualified name of the form
        "<group_name>-<band_name>", which will be loaded using
        :func:`load_filter`.
    wavelength : array
        A :func:`valid array <validate_wavelength_array>` of wavelengths
        that must cover the full range of the filter response.
    photon_weighted : bool
        Use :ref:`weights <weights>` appropriate for a photon-counting detector
        such as a CCD when this parameter is True.  Otherwise, use unit weights.
    interpolate : bool
        Allow interpolation of the tabulated function if necessary.
        Interpolation is required if two or more of the wavelengths where the
        filter response is tabulated fall between a consecutive pair of
        input wavelengths. Linear interpolation is then performed to estimate
        the input function at the undersampled filter response wavelengths.
        Interpolation has a performance impact when :meth:`evaluating
        <__call__>` a convolution, so is not enabled by default and can usually
        be avoided with finer sampling of the input function.
    units : astropy.units.Quantity or None
        When this parameter is not None, then any explicit units attached to
        the values passed to a :meth:`convolution <__call__>` must be
        convertible to these units. When values are passed without units
        they are assumed to be in these units.

    Attributes
    ----------
    response : :class:`FilterResponse`
        The filter response used for this convolution.
    input_units : :class:`astropy.units.Unit`
        Units expected for values passed to :meth:`__call__`.
    output_units : :class:`astropy.units.Unit`
        Units of :meth:`__call__` result.
    num_wavelength : int
        The number of wavelengths used to tabulate input functions.
    response_grid : numpy.ndarray
        Array of filter response values evaluated at each ``wavelength``.
    response_slice : slice
        Slice of the input wavelength grid used for convolution.
    interpolate_wavelength : numpy.ndarray or None
        Array of wavelengths where the input function will be interpolated.
    interpolate_response : numpy.ndarray or None
        Array of filter response values at each ``interpolate_wavelength``.
    interpolate_sort_order : numpy.ndarray or None
        Integer array specifying the sort order required to combine
        ``wavelength`` and ``interpolate_wavelength``.
    quad_wavelength : numpy.ndarray
        Array of wavelengths used for numerical quadrature, combining both
        ``wavelength`` and ``interpolate_wavelength``.
    quad_weight : :class:`astropy.units.Quantity` or None
        Array of weights corresponding to each ``quad_wavelength``.  Will be
        None if the parameter ``photon_weighted = False``.
    """
    def __init__(self, response, wavelength,
                 photon_weighted=True, interpolate=False, units=None):

        if isinstance(response, basestring):
            self.response = load_filter(response)
        else:
            self.response = response
        self._wavelength = validate_wavelength_array(wavelength, min_length=2)
        self.num_wavelength = len(self._wavelength)

        # Check if extrapolation would be required.
        under = (self._wavelength[0] > self.response._wavelength[0])
        over = (self._wavelength[-1] < self.response._wavelength[-1])
        if under or over:
            raise ValueError(
                'Wavelengths do not cover filter response {0:.1f}-{1:.1f} {2}.'
                .format(self.response._wavelength[0],
                        self.response._wavelength[-1],
                        default_wavelength_unit))

        # Find the smallest slice that covers the non-zero range of the
        # integrand.
        start, stop = 0, len(self._wavelength)
        if self._wavelength[0] < self.response._wavelength[0]:
            start = np.where(
                self._wavelength <= self.response._wavelength[0])[0][-1]
        if self._wavelength[-1] > self.response._wavelength[-1]:
            stop = 1 + np.where(
                self._wavelength >= self.response._wavelength[-1])[0][0]

        # Trim the wavelength grid if possible.
        self.response_slice = slice(start, stop)
        if start > 0 or stop < len(self._wavelength):
            self._wavelength = self._wavelength[self.response_slice]

        # Linearly interpolate the filter response to our wavelength grid.
        self.response_grid = self.response(self._wavelength)

        # Test if our grid is samples the response with sufficient density. Our
        # criterion is that at most one internal response wavelength (i.e.,
        # excluding the endpoints which we treat separately) falls between each
        # consecutive pair of our wavelength grid points.
        insert_index = np.searchsorted(
            self._wavelength, self.response._wavelength[1:])
        undersampled = np.diff(insert_index) == 0
        if np.any(undersampled):
            undersampled = 1 + np.where(undersampled)[0]
            if interpolate:
                # Interpolate at each undersampled wavelength.
                self.interpolate_wavelength = (
                    self.response._wavelength[undersampled])
                self.interpolate_response = self.response.response[undersampled]
                self.quad_wavelength = np.hstack(
                    [self._wavelength, self.interpolate_wavelength])
                self.interpolate_sort_order = np.argsort(self.quad_wavelength)
                self.quad_wavelength = self.quad_wavelength[
                    self.interpolate_sort_order]
            else:
                raise ValueError(
                    'Wavelengths undersample the response ' +
                    'and interpolate is False.')
        else:
            self.interpolate_wavelength = None
            self.interpolate_response = None
            self.interpolate_sort_order = None
            self.quad_wavelength = self._wavelength

        # Replace the quadrature endpoints with the actual filter endpoints
        # to eliminate any overrun.
        if self.quad_wavelength[0] < self.response._wavelength[0]:
            self.quad_wavelength[0] = self.response._wavelength[0]
        if self.quad_wavelength[-1] > self.response._wavelength[-1]:
            self.quad_wavelength[-1] = self.response._wavelength[-1]

        if photon_weighted:
            # Precompute the weights to use.
            self.quad_weight = self.quad_wavelength / _hc_constant.value
        else:
            self.quad_weight = None

        # Save the expected input value units.
        self.input_units = units
        if self.input_units is not None:
            # Calculate the output value units.
            if photon_weighted:
                self.output_units = self.input_units * _photon_weighted_unit
            else:
                self.output_units = self.input_units * default_wavelength_unit
        else:
            self.output_units = None


    def __call__(self, values, axis=-1, method='trapz', plot=False):
        """Evaluate the convolution for arbitrary tabulated function values.

        Parameters
        ----------
        values : array or :class:`astropy.units.Quantity`
            Array of function values to use.  Values are assumed to be
            tabulated on our wavelength grid.  Values can be multidimensional,
            in which case an array of convolution results is returned. If
            values have units, then these are propagated to the result.
        axis : int
            In case of multidimensional function values, this specifies the
            index of the axis corresponding to the wavelength dimension.
        method : str
            Specifies the numerical integration scheme to use and must be either
            'trapz' or 'simps', to select the corresponding
            ``scipy.integration`` function. The 'simps' method may be more
            accurate than the default 'trapz' method, but should be used with
            care since it is also less robust and more sensitive to the
            wavelength grids.
        plot : bool
            Displays a plot illustrating how the convolution integrand is
            constructed. Requires that the matplotlib package is installed
            and does not support multidimensional input values.  This option
            is primarily intended for debugging and to generate figures for
            the documentation.

        Returns
        -------
        float or numpy.ndarray or :class:`astropy.units.Quantity`
            Convolution integral result.  If the input values have units
            then these are propagated to the result, including the units
            associated with the photon weights (if these are selected).
            Otherwise, the result will be a plain float or numpy array.
            If the input is multidimensional, then so is the result but with the specified axis integrated out.
        """
        if method not in _filter_integration_methods.keys():
            raise ValueError(
                'Invalid method "{0}", pick one of {1}.'
                .format(method, _filter_integration_methods.keys()))

        values_no_units = np.asarray(values)
        if values_no_units.shape[axis] != self.num_wavelength:
            raise ValueError(
                'Expected {0} values along axis {1}.'
                .format(len(self._wavelength), axis))
        values_slice = [slice(None)] * len(values_no_units.shape)
        values_slice[axis] = self.response_slice
        values_no_units = values_no_units[values_slice]

        try:
            # If the input values have units, they must be convertible to
            # to our input units, which must be specified.
            values_no_units *= values.unit.to(self.input_units)
            input_has_units = True
        except AttributeError:
            # Input values have no units, so we assume that they are in
            # self.input_units if these are defined, or else that the caller
            # knows what they are doing.
            input_has_units = False
        except TypeError:
            # The input values have units but self.input_units is None.
            raise ValueError(
                'Must specify expected units for values with units.')
        except astropy.units.UnitConversionError:
            raise ValueError(
                'Values units {0} not convertible to {1}.'
                .format(values.unit, self.input_units))

        if plot:
            if len(values_no_units.shape) != 1:
                raise ValueError(
                    'Cannot plot convolution of multidimensional values.')
            import matplotlib.pyplot as plt
            ##fig, left_axis = plt.subplots()
            # Plot the filter response using the left-hand axis.
            plt.plot(self.response._wavelength,
                     self.response.response, 'rx-')
            plt.ylim(0., 1.1 * np.max(self.response.response))
            plt.xlabel('Wavelength (A)')
            plt.ylabel(
                '{0}-{1} Filter Response'.format(
                    self.response.meta['group_name'],
                    self.response.meta['band_name']))
            # Use the right-hand axis for the data being filtered.
            right_axis = plt.twinx()
            # A kludge to include the left-hand axis label in our legend.
            right_axis.plot([], [], 'r.-', label='filter')
            # Plot the input values using the right-hand axis.
            right_axis.set_ylabel('Integrand $dg/d\lambda \cdot R$')
            right_axis.plot(
                self._wavelength, values_no_units, 'bs-', label='input')
            right_axis.set_ylim(0., 1.1 * np.max(values_no_units))

        # Multiply values by the response.
        response_shape = np.ones_like(values_no_units.shape, dtype=int)
        response_shape[axis] = len(self.response_grid)
        integrand = values_no_units * self.response_grid.reshape(response_shape)

        if self.interpolate_wavelength is not None:
            # Interpolate the input values.
            interpolator = scipy.interpolate.interp1d(
                self._wavelength, values_no_units, axis=axis, kind='linear',
                copy=False, assume_sorted=True, bounds_error=True)
            interpolated_values = interpolator(self.interpolate_wavelength)
            if plot:
                # Show the interpolation locations.
                plt.scatter(
                    self.interpolate_wavelength, interpolated_values,
                    s=30, marker='o', edgecolor='b', facecolor='none',
                    label='interpolated')
            # Multiply interpolated values by the response.
            response_shape[axis] = len(self.interpolate_wavelength)
            interpolated_integrand = (
                interpolated_values *
                self.interpolate_response.reshape(response_shape))
            # Update the integrand with the interpolated values.
            integrand = np.concatenate(
                (integrand, interpolated_integrand), axis=axis)
            # Resort by wavelength.
            values_slice[axis] = self.interpolate_sort_order
            integrand = integrand[values_slice]

        if plot:
            # Plot integrand before applying weights, so we can re-use
            # the right-hand axis scale.
            plt.fill_between(
                self.quad_wavelength, integrand,
                color='g', lw=0, alpha=0.25)
            plt.plot(
                self.quad_wavelength, integrand,
                'g-', alpha=0.5, label='filtered')
            right_axis.legend(loc='center right')
            xpad = 0.05 * (
                self.quad_wavelength[-1] - self.quad_wavelength[0])
            plt.xlim(self._wavelength[0] - xpad,
                     self._wavelength[-1] + xpad)

        if self.quad_weight is not None:
            # Apply weights.
            response_shape[axis] = len(self.quad_weight)
            integrand *= self.quad_weight.reshape(response_shape)

        integrator = _filter_integration_methods[method]
        integral = integrator(
            y=integrand, x=self.quad_wavelength, axis=axis)

        if input_has_units:
            # Apply the output units.
            integral = integral * self.output_units
        return integral


class FilterSequence(collections.Sequence):
    """Immutable sequence of filter responses.

    Sequences should normally be created by calling :func:`load_filters`.
    Objects implement the `immutable sequence
    <https://docs.python.org/2/library/collections.html
    #collections-abstract-base-classes>`__ API, in addition to the methods
    listed here.

    A filter sequence's :meth:`get_ab_maggies` and :meth:`get_ab_magnitudes`
    methods return their results in a :class:`Table <astropy.table.Table>` and
    are convenient for calculating convolutions in several bands for
    multiple spectra.  For example, given the following 4 (identical) spectra
    covering the SDSS filters:

    >>> num_spectra, num_pixels = 4, 500
    >>> wlen = np.linspace(2000, 12000, num_pixels) * default_wavelength_unit
    >>> flux = np.ones((num_spectra, num_pixels)) * 1e-17 * default_flux_unit

    We can now calculate their magnitudes in all bands with one function:

    >>> sdss = load_filters('sdss2010-*')
    >>> mags = sdss.get_ab_magnitudes(flux, wlen)

    Refer to the :mod:`astropy docs <astropy.table>` for details on working
    with Tables.  For example, to pretty-print the magnitudes with a
    precision of 0.001:

    >>> formats = dict((n, '%.3f') for n in sdss.names)
    >>> mags.write(None, format='ascii.fixed_width', formats=formats)
    | sdss2010-u | sdss2010-g | sdss2010-r | sdss2010-i | sdss2010-z |
    |     22.340 |     21.742 |     21.141 |     20.718 |     20.338 |
    |     22.340 |     21.742 |     21.141 |     20.718 |     20.338 |
    |     22.340 |     21.742 |     21.141 |     20.718 |     20.338 |
    |     22.340 |     21.742 |     21.141 |     20.718 |     20.338 |

    Parameters
    ----------
    responses : iterable
        Response objects to include in this sequence. Objects are copied to
        an internal list.

    Attributes
    ----------
    names : list of str
        List of the filter response names in this sequence, with the format
        "<group_name>-<band_name>".
    effective_wavelengths : astropy.units.Quantity
        List of the effective wavelengths for the filter responses in this
        sequence, with the default wavelength units.
    """
    def __init__(self, responses):
        self._responses = list(responses)


    def __contains__(self, item):
        return item in self._responses


    def __len__(self):
        return len(self._responses)


    def __iter__(self):
        return iter(self._responses)


    def __getitem__(self, key):
        return self._responses[key]


    @property
    def names(self):
        return [r.name for r in self]


    @property
    def effective_wavelengths(self):
        return [
            r.effective_wavelength.value for r in self
            ] * default_wavelength_unit


    def get_ab_maggies(self, spectrum, wavelength=None, axis=-1):
        """Calculate a spectrum's relative AB flux convolutions.

        Calls :meth:`FilterResponse.get_ab_maggies` for each filter in this
        sequence and returns the results in a structured array.

        Use :meth:`get_ab_magnitudes` for the corresponding AB magnitudes.

        Parameters
        ----------
        spectrum : callable or array or :class:`astropy.units.Quantity`
            See :meth:`get_ab_maggies` for details.
        wavelength : array or :class:`astropy.units.Quantity` or None
            See :meth:`get_ab_maggies` for details.
        axis : int
            See :meth:`get_ab_maggies` for details.

        Returns
        -------
        astropy.table.Table
            A table of results with column names corresponding to canonical
            filter names of the form "<group_name>-<band_name>". If the input
            spectrum data is multidimensional, its first index is mapped to rows
            of the returned table.
        """
        t = astropy.table.Table(meta=dict(
            description='Created by speclite <speclite.readthedocs.org>'))
        for r in self:
            data = r.get_ab_maggies(spectrum, wavelength, axis)
            if np.isscalar(data):
                data = [data]
            t.add_column(astropy.table.Column(name=r.name, data=data))
        return t


    def get_ab_magnitudes(self, spectrum, wavelength=None, axis=-1):
        """Calculate a spectrum's AB magnitude.

        Calls :meth:`FilterResponse.get_ab_magnitude` for each filter in this
        sequence and returns the results in a structured array.

        Parameters
        ----------
        spectrum : callable or array or :class:`astropy.units.Quantity`
            See :meth:`get_ab_magnitude` for details.
        wavelength : array or :class:`astropy.units.Quantity` or None
            See :meth:`get_ab_magnitude` for details.
        axis : int
            See :meth:`get_ab_magnitude` for details.

        Returns
        -------
        astropy.table.Table
            A table of results with column names corresponding to canonical
            filter names of the form "<group_name>-<band_name>". If the input
            spectrum data is multidimensional, its first index is mapped to rows
            of the returned table.
        """
        t = astropy.table.Table(meta=dict(
            description='Created by speclite <speclite.readthedocs.org>'))
        for r in self:
            data = r.get_ab_magnitude(spectrum, wavelength, axis)
            if data.shape == ():
                data = [data]
            t.add_column(astropy.table.Column(name=r.name, data=data))
        return t


def load_filters(*names):
    """Load a sequence of filters by name.

    For example, to load all the ``sdss2010`` filters:

    >>> sdss = load_filters('sdss2010-*')
    >>> sdss.names
    ['sdss2010-u', 'sdss2010-g', 'sdss2010-r', 'sdss2010-i', 'sdss2010-z']

    Names are intepreted according to the following rules:

    - A canonical name of the form "<group_name>-<band_name>" loads the
      corresponding single standard filter response.
    - A group name with a wildcard, "<group_name>-\*", loads all the standard
      filters in a group, ordered by increasing effective wavelength.
    - A filename ending with the ".ecsv" extension loads a custom filter
      response from the specified file.

    Note that custom filters must be specified individually, even if they
    all belong to the same group.

    Parameters
    ----------
    \*names
        Variable length list of names to include.  Each name must be in one
        of the formats described above.

    Returns
    -------
    FilterSequence
        An immutable :class:`FilterSequence` object containing the requested
        filters in the order they were specified.
    """
    # Replace any group wildcards with the corresponding canonical names.
    filters_path = astropy.utils.data._find_pkg_data_path('data/filters/')
    names_to_load = []
    for name in names:
        group_match = _group_wildcard.match(name)
        if group_match:
            # Scan data/filters/ for bands in this group.
            band_names = []
            band_weff = []
            file_names = glob.glob(
                os.path.join(filters_path, '{0}.ecsv'.format(name)))
            for file_name in file_names:
                full_name, _ = os.path.splitext(os.path.basename(file_name))
                band_names.append(full_name)
                response = load_filter(full_name)
                band_weff.append(response.effective_wavelength)
            # Add bands in order of increasing effective wavelength.
            names_to_load.extend(
                [name for (weff, name) in sorted(zip(band_weff, band_names))])
        else:
            names_to_load.append(name)
    # Load filters and return them wrapped in a FilterSequence.
    responses = []
    for name in names_to_load:
        responses.append(load_filter(name))
    return FilterSequence(responses)


def load_filter(name, load_from_cache=True, verbose=False):
    """Load a single filter response by name.

    See :doc:`/filters` for details on the filter response file format and
    the available standard filters.

    A filter response is normally only loaded from disk the first time this
    function is called, and subsequent calls immediately return the same
    cached object.  Use the ``verbose`` option for details on how a filter
    is loaded:

    >>> rband = load_filter('sdss2010-r')
    >>> rband = load_filter('sdss2010-r', verbose=True)
    Returning cached filter response "sdss2010-r"

    Use :func:`load_filters` to load a sequence of filters from one or
    more filter groups.

    Parameters
    ----------
    name : str
        Name of the filter response to load, which should normally have the
        format "<group_name>-<band_name>", and refer to one of the reference
        filters described :doc:`here </filters>`.  Otherwise, the name of
        any file in the `ECSV format
        <https://github.com/astropy/astropy-APEs/blob/master/APE6.rst>`__
        and containing the required fields can be provided.  The existence
        of the ".ecsv" extension is used to distinguish between these cases
        and any other extension is considered an error.
    load_from_cache : bool
        Return a previously cached response object if available.  Otherwise,
        always load the file from disk.
    verbose : bool
        Print verbose information about how this filter is loaded.

    Returns
    -------
    FilterResponse
        A :class:`FilterResponse` object for the requested filter.

    Raises
    ------
    ValueError
        File does not exist or custom file has wrong extension.
    RuntimeError
        File is incorrectly formatted.  This should never happen for the
        files included in the source code distribution.
    """
    if load_from_cache and name in _filter_cache:
        if verbose:
            print('Returning cached filter response "{0}"'.format(name))
        return _filter_cache[name]
    # Is this a non-standard filter file?
    base_name, extension = os.path.splitext(name)
    if extension not in ('', '.ecsv'):
        raise ValueError(
            'Invalid extension for filter file name: "{0}".'.format(extension))
    if extension:
        file_name = name
    else:
        file_name = astropy.utils.data._find_pkg_data_path(
            'data/filters/{0}.ecsv'.format(name))
    if not os.path.isfile(file_name):
        raise ValueError('No such filter file "{0}".'.format(file_name))
    if verbose:
        print('Loading filter response from "{0}".'.format(file_name))
    table = astropy.table.Table.read(
        file_name, format='ascii.ecsv', guess=False)

    if 'wavelength' not in table.colnames:
        raise RuntimeError('Table is missing required wavelength column.')
    wavelength_column = table['wavelength']
    if wavelength_column.unit is None:
        raise RuntimeError('No wavelength column unit specified.')
    wavelength = wavelength_column.data * wavelength_column.unit

    if 'response' not in table.colnames:
        raise RuntimeError('Table is missing required response column.')
    response_column = table['response']
    if response_column.unit is not None:
        raise RuntimeError('Response column has unexpected units.')
    response = response_column.data

    return FilterResponse(wavelength, response, table.meta)


def plot_filters(responses, wavelength_unit=None,
                 wavelength_limits=None, wavelength_scale='linear',
                 legend_loc='upper right', cmap='nipy_spectral'):
    """Plot one or more filter response curves.

    The matplotlib package must be installed to use this function. The
    :meth:`show <matplotlib.pylot.show` method is not called after creating
    the plot to allow convenient customization and saving. As a result, you will
    normally need to call this method yourself.

    Parameters
    ----------
    responses : :class:`FilterSequence`
        The sequence of filters to plot, normally obtained by calling
        :func:`load_filters`.
    wavelength_unit : :class:`astropy.units.Unit`
        Convert values along the wavelength axis to the specified unit, or
        leave them as :attr:`default_wavelength_unit` if this parameter is None.
    wavelength_limits : tuple or None
        Plot limits to use on the wavelength axis, or select limits
        automatically if this parameter is None.  Units are optional.
    wavelength_scale : str
        Scaling to use for the wavelength axis. See
        :func:`matplotlib.pyplot.yscale` for details.
    legend_loc : str
        Location of the legend to plot, or do not display any legend if this
        value is None.  See :func:`matplotlib.pyplot.legend` for details.
    cmap : str or :class:`matplotlib.colors.Colormap`
        Color map to use for plotting each filter band.  Colors are assigned
        based on each band's effective wavelength, so a spectral color map
        (from blue to red) will give nice results.
    """
    if wavelength_unit is None:
        wavelength_unit = default_wavelength_unit

    # Look up the range of effective wavelengths for this set of filters.
    effective_wavelengths = responses.effective_wavelengths
    min_wlen, max_wlen = min(effective_wavelengths), max(effective_wavelengths)

    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    cmap = cm.get_cmap(cmap)
    fig, ax = plt.subplots()
    plt.xscale(wavelength_scale)
    if wavelength_limits is not None:
        try:
            wlen_min, wlen_max = wavelength_limits
        except ValueError:
            raise ValueError('Invalid wavelength limits.')
        try:
            wlen_min = wlen_min.to(wavelength_unit).value
        except astropy.units.UnitConversionError:
            raise ValueError('Invalid wavelength_unit.')
        except AttributeError:
            pass
        try:
            wlen_max = wlen_max.to(wavelength_unit).value
        except astropy.units.UnitConversionError:
            raise ValueError('Invalid wavelength_unit.')
        except AttributeError:
            pass
        plt.xlim(wlen_min, wlen_max)

    for response, wlen in zip(responses, effective_wavelengths):
        if max_wlen > min_wlen:
            # Use an approximate spectral color for each band.
            c = cmap(0.1 + 0.8 * (wlen - min_wlen) / (max_wlen - min_wlen))
        else:
            c = 'green'
        wlen = response._wavelength * default_wavelength_unit
        try:
            wlen = wlen.to(wavelength_unit)
        except astropy.units.UnitConversionError:
            raise ValueError('Invalid wavelength_unit.')

        plt.fill_between(wlen.value, response.response, color=c, alpha=0.25)
        plt.plot(wlen.value, response.response,
                 color=c, alpha=0.5, label=response.name)

    plt.xlabel('Wavelength [{0}]'.format(wavelength_unit))
    plt.ylabel('Filter Response')
    if legend_loc is not None:
        plt.legend(loc = legend_loc)
    plt.grid()


def filter_sampling_explanatory_plot(save=None):
    """Generate an explanatory plot for the documentation.

    Requires that the matplotlib package is installed.

    The generated figure appears in the :ref:`sampling` section.

    Parameters
    ----------
    save : str or None
        Name of the file where this plot should be saved.
    """
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(15, 4))
    #
    wlen = [4500, 7400] * default_wavelength_unit
    rconv = FilterConvolution(
        'bessell-V', wlen, interpolate=True, units=default_flux_unit)
    flux = [1., 1.] * default_flux_unit
    plt.subplot(1, 3, 1)
    c1 = rconv(flux, plot=True).cgs
    #
    wlen = np.linspace(4500, 7400, 30) * default_wavelength_unit
    rconv = FilterConvolution('bessell-V', wlen, units=default_flux_unit)
    flux = np.ones_like(wlen.value) * default_flux_unit
    plt.subplot(1, 3, 2)
    c2 = rconv(flux, plot=True).cgs
    #
    wlen = np.linspace(4500, 7400, 9) * default_wavelength_unit
    rconv = FilterConvolution(
        'bessell-V', wlen, interpolate=True, units=default_flux_unit)
    flux = np.ones_like(wlen.value) * default_flux_unit
    plt.subplot(1, 3, 3)
    c3 = rconv(flux, plot=True).cgs
    #
    print('c2-c1 error = {0:.3f}%, c3-c1 error = {1:.3f}%'
          .format(1e2 * abs(c2 - c1) / c1, 1e2 * abs(c3 - c1) / c1))
    #
    plt.tight_layout()
    if save:
        plt.savefig(save)
