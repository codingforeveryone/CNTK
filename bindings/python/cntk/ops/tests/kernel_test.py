# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root
# for full license information.
# ==============================================================================

"""
Unit tests for kernel operations, tested for the forward and the backward pass
"""

from __future__ import division
import numpy as np
import pytest
import cntk as C
from .ops_test_utils import unittest_helper, _test_unary_op, AA, precision, PRECISION_TO_TYPE, constant, cntk_device
from cntk.ops import AVG_POOLING, MAX_POOLING, MAX_UNPOOLING
from cntk.internal import sanitize_dtype_cntk

CONVOLUTION_OPERANDS = [
    ([[[5., 6.],  # (1, 2, 2) map
       [3., 4.]]],
     [[[1., 2.],  # (1, 2, 2) input operand
       [7., 8.]]],
     True),       # Use input shape with inferred dimension
    ([[[1., 2.],  # (3, 2, 2) map
       [3., 4.]],
      [[1., 2.],
       [3., 4.]],
      [[1., 2.],
       [3., 4.]]],
     [[[1., 2.],  # (3, 2, 2) input operand
       [3., 4.]],
      [[5., 6.],
       [7., 8.]],
      [[9., 10.],
       [11., 12.]]],
      False)      # Do not use input shape with inferred dimension
]


@pytest.mark.parametrize("convolution_map, convolution_input, use_input_shape_with_inferred_dimension", CONVOLUTION_OPERANDS)
def test_op_convolution_without_padding(convolution_map, convolution_input, use_input_shape_with_inferred_dimension, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]
    dev = cntk_device(device_id)

    conv_map = AA(convolution_map, dtype=dt)
    conv_input = AA(convolution_input, dtype=dt)

    flipped_conv_map = conv_map[..., ::-1, ::-1]

    from scipy import signal
    expected_forward = AA([signal.convolve(flipped_conv_map, conv_input, mode='valid')])

    backward = AA(conv_map)

    conv_input_shape = conv_input.shape
    if use_input_shape_with_inferred_dimension:
        conv_input_shape = tuple(-1 for x in conv_input_shape)

    a = C.input_variable(shape=conv_input_shape,
                dtype=sanitize_dtype_cntk(precision),
                needs_gradient=True,
                name='a')

    conv_input.shape = (1,) + conv_input.shape # adding batch and channel axis
    conv_map.shape = (1,) + conv_map.shape

    constant_map = constant(value=conv_map, device=dev)

    from cntk import convolution
    input_op = convolution(constant_map, a, auto_padding=[False])

    forward_input = {a: conv_input}
    expected_backward = {a: backward}

    unittest_helper(input_op, forward_input, expected_forward,
                    expected_backward, device_id=device_id, precision=precision)


ASYM_CONVOLUTION_DATA = [
    ([1, 1, 3, 3], # input_size
     [1, 2, 2], # convolution size
     [[[[ 19, 25, 10],
        [ 37, 43, 16],
        [ 7, 8, 0]]]]) # result
]
# this test handles convolution with asymmetric padding, in particular, with auto_padding is set to True
# and the kernel shape is even
@pytest.mark.parametrize("input_size, conv_size, result", ASYM_CONVOLUTION_DATA)
def test_asym_convolution(input_size, conv_size, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]
    dev = cntk_device(device_id)

    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(total_size, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.input_variable(shape=input_operand.shape[1:],
                dtype=sanitize_dtype_cntk(precision),
                needs_gradient=False,
                name='a')

    # do the same for convolution kernel
    total_size = np.prod(conv_size)
    y = np.arange(total_size, dtype=dt)
    conv_map = constant(value=y.reshape(conv_size), device=dev)

    from cntk import convolution
    input_op = convolution(conv_map, a, auto_padding=[True])

    forward_input = {a: input_operand}
    expected_forward = AA(result)

    unittest_helper(input_op, forward_input, expected_forward,
                    None, device_id=device_id, precision=precision)


POOLING_GEOMETRY_DATA = [
    ([1, 1, 6, 6], # input_size
     (1, 5, 5), # pooling_window
     (1, 3, 3), # strides
     [True], # padding flag
     [[[[ 21,   23],
        [ 33,   35]]]], # result
     True), # Use input shape with inferred dimension
    ([1, 1, 8, 8],
     (1, 4, 4),
     (1, 5, 5),
     [False],
     [[[[ 27 ]]]],
     False),
    ([1, 1, 6, 6],
     (1, 4, 4),
     (1, 2, 2),
     [True, False],
     [[[[ 15, 17],
        [ 27, 29],
        [ 33, 35]]]],
     True)
]
# the pooling geometry test also tests convolution geometry since they go through the same path
# in the CPU code
@pytest.mark.parametrize("input_size, pooling_window, strides, padding, result, use_input_shape_with_inferred_dimension", POOLING_GEOMETRY_DATA)
def test_op_pooling_geometry(input_size, pooling_window, strides, padding, result, use_input_shape_with_inferred_dimension, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]

    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(total_size, dtype=dt)
    input_operand = x.reshape(input_size)

    pool_input_shape = input_operand.shape[1:]
    if use_input_shape_with_inferred_dimension:
        pool_input_shape = tuple(-1 for x in pool_input_shape)

    a = C.input_variable(shape=pool_input_shape,
                dtype=sanitize_dtype_cntk(precision),
                needs_gradient=False,
                name='a')

    from cntk import pooling
    input_op = pooling(a, MAX_POOLING, pooling_window, strides, auto_padding=padding)

    forward_input = {a: input_operand}
    expected_forward = AA(result)

    unittest_helper(input_op, forward_input, expected_forward,
                    None, device_id=device_id, precision=precision)

AVG_POOLING_DATA = [
    ([1, 2, 2, 4, 3], # input_size
     (2, 2, 1), # pooling_window
     (2, 2, 1), # strides
     [[[[  8.5,   9.5,  10.5],
        [ 14.5,  15.5,  16.5]]],
      [[[ 32.5,  33.5,  34.5],
        [ 38.5,  39.5,  40.5]]]]), # result
    ([1, 1, 2, 2 ,4],
     (2, 2, 1),
     (2, 2, 1),
     [[[[  7.,   8.,   9.,  10.]]]])
]
@pytest.mark.parametrize("input_size, pooling_window, strides, result", AVG_POOLING_DATA)
def test_op_avg_pooling(input_size, pooling_window, strides, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]

    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(1, total_size + 1, 1, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.sequence.input_variable(shape=input_operand.shape[2:],
                         dtype=sanitize_dtype_cntk(precision),
                         needs_gradient=True,
                         name='a')
                
    backward = (1 / np.prod(pooling_window)) * np.ones_like(input_operand)

    from cntk import pooling
    input_op = pooling(a, AVG_POOLING, pooling_window, strides, auto_padding=[True])

    forward_input = {a: input_operand}

    expected_forward = AA([result])
    expected_backward = {a: backward}

    unittest_helper(input_op, forward_input, expected_forward,
                expected_backward, device_id=device_id, precision=precision)

MAX_POOLING_DATA = [
    ([1, 2, 2, 4, 3], # input_size
     (2, 2, 1), # pooling_window
     (2, 2, 1), # strides
     [False],   # autopad
     [[[[ 16.,  17.,  18.],
         [ 22.,  23.,  24.]]],
       [[[ 40.,  41.,  42.],
         [ 46.,  47.,  48.]]]]), # result

    ([1, 2, 4, 4, 4],
     (2, 2, 2),
     (2, 2, 2),
     [False],
     [[[[  22.,   24.],
        [  30.,   32.]],
       [[  54.,   56.],
        [  62.,   64.]]],
      [[[  86.,   88.],
        [  94.,   96.]],
       [[ 118.,  120.],
        [ 126.,  128.]]]]),

    ([1, 1, 1, 8, 8],
     (5, 5),
     (2, 2),
     [True],
     [[[[ 19.,  21.,  23.,  24.],
        [ 35.,  37.,  39.,  40.],
        [ 51.,  53.,  55.,  56.],
        [ 59.,  61.,  63.,  64.]]]])
]


@pytest.mark.parametrize("input_size, pooling_window, strides, autopad, result", MAX_POOLING_DATA)
def test_op_max_pooling(input_size, pooling_window, strides, autopad, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]

    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(1, total_size + 1, 1, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.sequence.input_variable(shape=input_operand.shape[2:],
                         dtype=sanitize_dtype_cntk(precision),
                         needs_gradient=True,
                         name='a')

    result_array = np.asarray(result, dtype=dt)
    max_elements = result_array.reshape(result_array.size).tolist()

    # place 1.0s where maximum elements are
    backward = np.zeros_like(input_operand)
    for element in max_elements:
        backward += np.asarray(input_operand == element)

    from cntk import pooling
    input_op = pooling(a, MAX_POOLING, pooling_window, strides, autopad)

    forward_input = {a: input_operand}

    expected_forward = AA([result])
    expected_backward = {a: backward}

    unittest_helper(input_op,
                forward_input, expected_forward, expected_backward,
                device_id=device_id, precision=precision)


@pytest.mark.parametrize("input_size, pooling_window, strides, autopad, result", MAX_POOLING_DATA)
def test_op_max_unpooling(input_size, pooling_window, strides, autopad, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]


    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(1, total_size + 1, 1, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.sequence.input_variable(shape=input_operand.shape[2:],
                         dtype=sanitize_dtype_cntk(precision),
                         needs_gradient=True,
                         name='a')

    pooling_result = np.asarray(result, dtype=dt)
    max_elements = pooling_result.reshape(pooling_result.size).tolist()

    # place 1.0s where maximum elements are
    backward = np.zeros_like(input_operand)
    for element in max_elements:
        backward += np.asarray(input_operand == element)

    from cntk import pooling, unpooling
    p = pooling(a, MAX_POOLING, pooling_window, strides, autopad)
    u = unpooling(p, a, MAX_UNPOOLING, pooling_window, strides, autopad)
    q = pooling(u, MAX_POOLING, pooling_window, strides, autopad)

    forward_input = {a: input_operand}

    expected_forward = backward * input_operand
    expected_backward = {a: backward}

    unittest_helper(u,
                forward_input, expected_forward, expected_backward,
                device_id=device_id, precision=precision)
    assert np.allclose(p.eval(forward_input), q.eval(forward_input))

POOLING_CEIL_DATA = [
    ([1, 1, 8, 8],                   # input_size
     (2, 2),                            # pooling_window
     (2, 2),                            # strides
     [[[[10.,  12.,  14.,  16.],
        [26.,  28.,  30.,  32.],
        [42.,  44.,  46.,  48.],
        [58.,  60.,  62.,  64.]]]]),    # result
    ([1, 1, 8, 8],
     (3, 3),
     (2, 2),
     [[[[19., 21., 23., 24.],
        [35., 37., 39., 40.],
        [51., 53., 55., 56.],
        [59., 61., 63., 64.]]]]),
]


@pytest.mark.parametrize("input_size, pooling_window, strides, result", POOLING_CEIL_DATA)
def test_op_pooling_ceil(input_size, pooling_window, strides, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]

    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(1, total_size + 1, 1, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.input_variable(shape=input_operand.shape[1:], dtype=sanitize_dtype_cntk(precision), needs_gradient=True, name='a')

    result_array = np.asarray(result, dtype=dt)
    max_elements = result_array.reshape(result_array.size).tolist()

    # place 1.0s where maximum elements are
    backward = np.zeros_like(input_operand)
    for element in max_elements:
        backward += np.asarray(input_operand == element)

    from cntk import pooling
    input_op = pooling(a, MAX_POOLING, pooling_window, strides, ceil_out_dim=True)

    forward_input = {a: input_operand}

    expected_forward = AA(result)
    expected_backward = {a: backward}

    unittest_helper(input_op, forward_input, expected_forward, expected_backward, device_id=device_id,
                    precision=precision)

POOLING_AVG_INCLUDE_PAD_DATA = [
    ([1, 1, 7, 7],
     (3, 3),
     (3, 3),
     [[[[20./9, 45./9, 40./9],
        [135./9, 225./9, 165./9],
        [160./9, 255./9, 180./9]]]]),
]


@pytest.mark.parametrize("input_size, pooling_window, strides, result", POOLING_AVG_INCLUDE_PAD_DATA)
def test_op_average_pooling_include_pad(input_size, pooling_window, strides, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]

    total_size = np.prod(input_size)
    x = np.arange(1, total_size + 1, 1, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.input_variable(shape=input_operand.shape[1:], dtype=sanitize_dtype_cntk(precision), needs_gradient=True, name='a')

    backward = (1 / np.prod(pooling_window)) * np.ones_like(input_operand)

    from cntk import pooling
    input_op = pooling(a, AVG_POOLING, pooling_window, strides, auto_padding=[True], include_pad=True)

    forward_input = {a: input_operand}

    expected_forward = AA(result)
    expected_backward = {a: backward}

    unittest_helper(input_op, forward_input, expected_forward, expected_backward,
                    device_id=device_id, precision=precision)

# ROI pooling test setup
# --- forward ---
# input convFeatureMap 3x3 map, values [[1,2,3][4,5,6][7,8,9]]
# input rois 4x1, values (x, y, w, h) = (1/3, 1/3, 2/3, 2/3)
# roiOutputShape 3 x 3
# expected output 3x3 map, values [[5,6,6][8,9,9][8,9,9]]
# --- backward ---
# gradient 3x3 map, values [[1,1,1][1,1,1][1,1,1]]
# expected output gradient 3x3 map, values [[0,0,0][0,1,2][0,2,4]]
ROIPOOLING_OPERANDS = [
    ([[[1., 2., 3.],       # (1, 3, 3) input operand (conv feature map)
       [4., 5., 6.],
       [7., 8., 9.]]],
     [[1, 1, 2, 2]],       # (4) input roi (x1, y1, x2, y2), where (x1, y1) is top left coordinate and (x2, y2) bottom right coordinate.
     [[[5., 6., 6.],       # (1, 3, 3) expected forward output
       [8., 9., 9.],
       [8., 9., 9.]]],
     [[[0., 0., 0.],       # (1, 3, 3) expected backward output (gradient input is all 1s)
       [0., 1., 2.],
       [0., 2., 4.]]])
]

@pytest.mark.parametrize("input_map, input_rois, expected_fwd, expected_bkwd", ROIPOOLING_OPERANDS)
def test_op_maxroipooling(input_map, input_rois, expected_fwd, expected_bkwd, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]

    # AA == as numpy array
    conv_input        = AA(input_map, dtype=dt)
    roi_input         = AA(input_rois, dtype=dt)
    exp_fwd_value     = AA(expected_fwd, dtype=dt)
    exp_bkwd_value    = AA(expected_bkwd, dtype=dt)

    # adding batch, sequence and roi axis
    exp_fwd_value.shape  = (1,1) + exp_fwd_value.shape
    exp_bkwd_value.shape = (1,) + exp_bkwd_value.shape

    # I == define cntk input variables
    a = C.input_variable(shape=conv_input.shape,
                dtype=sanitize_dtype_cntk(precision),
                needs_gradient=True,
                name='a')

    b = C.input_variable(shape=roi_input.shape,
                dtype=sanitize_dtype_cntk(precision),
                needs_gradient=False,
                name='b')

    # adding batch and sequence axis
    conv_input.shape     = (1,) + conv_input.shape
    roi_input.shape      = (1,) + roi_input.shape

    from cntk import roipooling
    input_op = roipooling(a, b, C.MAX_POOLING, (3,3), 1.)

    forward_input = {a: conv_input, b: roi_input}
    expected_backward = {a: exp_bkwd_value}

    unittest_helper(input_op,
                    forward_input, exp_fwd_value, expected_backward,
                    device_id=device_id, precision=precision)

CONVOLUTION_TRANSPOSE_DATA = [
    ([1, 1, 3, 3], # input_size
     [1, 2, 2], # convolution size
     [[[[ 0, 0, 1, 2],
        [ 0, 5, 11, 11],
        [ 6, 23, 29, 23],
        [ 12, 32, 37, 24]]]]) # result
]
# this test handles convolution transpose, without specifying output shape
@pytest.mark.parametrize("input_size, conv_size, result", CONVOLUTION_TRANSPOSE_DATA)
def test_convolution_transpose(input_size, conv_size, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]
    dev = cntk_device(device_id)

    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(total_size, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.input_variable(shape=input_operand.shape[1:],
                dtype=sanitize_dtype_cntk(precision),
                needs_gradient=False,
                name='a')

    # do the same for convolution kernel
    total_size = np.prod(conv_size)
    y = np.arange(total_size, dtype=dt)
    conv_map = constant(value=y.reshape(conv_size), device=dev)

    from cntk import convolution_transpose
    input_op = convolution_transpose(conv_map, a, auto_padding=[False])

    forward_input = {a: input_operand}
    expected_forward = AA(result)

    unittest_helper(input_op, forward_input, expected_forward,
                    None, device_id=device_id, precision=precision)

CONVOLUTION_TRANSPOSE_OUTPUT_DATA = [
    ([1, 1, 3, 3], # input_size
     [1, 3, 3], # convolution size
     [[[[ 0, 3, 4, 11, 8, 10],
        [ 3, 12, 11, 28, 19, 26],
        [ 12, 27, 16, 35, 20, 25],
        [ 27, 60, 35, 76, 43, 56], 
        [ 24, 51, 28, 59, 32, 40]]]]) # result
]
# this test handles convolution transpose, without specifying output shape
@pytest.mark.parametrize("input_size, conv_size, result", CONVOLUTION_TRANSPOSE_OUTPUT_DATA)
def test_convolution_transpose_with_output(input_size, conv_size, result, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]
    dev = cntk_device(device_id)

    # fill input operand with a sequence 1,2,3,... til total size and then
    # resize to input_size
    total_size = np.prod(input_size)
    x = np.arange(total_size, dtype=dt)
    input_operand = x.reshape(input_size)

    a = C.input_variable(shape=input_operand.shape[1:],
                dtype=sanitize_dtype_cntk(precision),
                needs_gradient=False,
                name='a')

    # do the same for convolution kernel
    total_size = np.prod(conv_size)
    y = np.arange(total_size, dtype=dt)
    conv_map = constant(value=y.reshape(conv_size), device=dev)

    from cntk import convolution_transpose
    input_op = convolution_transpose(conv_map, a, auto_padding=[True], strides=2, output_shape=(1,5,6))

    forward_input = {a: input_operand}
    expected_forward = AA(result)

    unittest_helper(input_op, forward_input, expected_forward,
                    None, device_id=device_id, precision=precision)


def test_conv_incorrect_shapes():
    input = C.input_variable(())    
    with pytest.raises(ValueError):
        h = C.layers.Convolution(filter_shape=(5,5), num_filters=8, strides=(1,1), pad=True)(input)
    with pytest.raises(ValueError):
        h = C.layers.MaxPooling(filter_shape=(2,2), strides=(2,2))(input)

    input = C.input_variable(28)    
    with pytest.raises(ValueError):
        h = C.layers.Convolution(filter_shape=(5,5), num_filters=8, strides=(1,1), pad=True)(input)
    with pytest.raises(ValueError):
        h = C.layers.MaxPooling(filter_shape=(2,2), strides=(2,2))(input)

def test_conv_cudnn_batch_size_change(device_id):
    if device_id == -1:
        pytest.skip('Test only runs on GPU')

    np.random.seed(0)
    input_shape = (1, 16, 100)
    input1 = C.sequence.input_variable(input_shape, needs_gradient=True, sequence_axis=C.Axis.new_unique_dynamic_axis('c'))
    input2 = C.sequence.input_variable(input_shape, needs_gradient=True, sequence_axis=C.Axis.new_unique_dynamic_axis('q'))
    conv = C.layers.Convolution2D((5,8), 100, activation=C.relu, init=C.glorot_uniform(), bias=True, init_bias=0)
    output = C.reduce_sum(conv(input1), axis=C.Axis.all_axes()) + C.reduce_sum(conv(input2), axis=C.Axis.all_axes())
    num_batches = 100 # change to greater value for a more thorough test
    batch_size = 1
    max_seq_len = [100, 10]
    for batch in range(num_batches):
        seq_lens = [[int(x*msl+1) for x in np.random.random((batch_size))] for msl in max_seq_len]
        output.grad({input1:[np.random.random((sl,) + input_shape).astype(np.float32) for sl in seq_lens[0]],
                     input2:[np.random.random((sl,) + input_shape).astype(np.float32) for sl in seq_lens[1]]})

FREE_STATIC_AXES_CONVOLUTION_DATA = [
    # 2D convolution with single free static axis.
    ([5, 101, 151], # warmup_input_size: Defines the input size used for first run with free static axes. 3- and 4-element vector for 2D and 3D convolution, respectively. 
     [200],         # free_dimension_increment: Increments to the input size for the second/actual/test run. Length defines the number of free static axes.
     [5, 5],        # filter_size: kernel size for convolution. Length defines 2D or 3D convolution.
     128            # num_output_channels
     ),
    # 2D convolution with two free static axes.
    ([3, 51, 101], 
     [100, 121], 
     [3, 3], 
     128
     ),
    # 3D convolution with three free static axes.
    ([3, 51, 101, 71],
     [100, 21, 31],
     [3, 3, 3],
     16
     ),
    # 3D convolution with two free static axes.
    ([5, 51, 61, 91],
     [20, 12],
     [3, 3, 3],
     8
     ),
    # 3D convolution with single free static axis.
    ([2, 101, 121, 151],
     [10],
     [3, 3, 3],
     8
     )
]
# This test point exercises 2D and 3D convolution with single and multiple free static axes, and ensures that the result is the same as with fixed axes.
@pytest.mark.parametrize("warmup_input_size, free_dimension_increment, filter_size, num_output_channels", FREE_STATIC_AXES_CONVOLUTION_DATA)
def test_conv_free_static_axes(warmup_input_size, free_dimension_increment, filter_size, num_output_channels, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]
    dev = cntk_device(device_id)

    np.random.seed(0)

    conv_size = tuple([num_output_channels, warmup_input_size[0]]+filter_size)
    total_size = np.prod(conv_size)
    y = np.arange(total_size, dtype=dt)
    conv_map = constant(value=y.reshape(conv_size), device=dev)

    reference_input_size = tuple(warmup_input_size[:-len(free_dimension_increment)] +
                           [x+y for x,y in zip(warmup_input_size[-len(free_dimension_increment):], free_dimension_increment)])

    a_ref = C.input_variable(shape=reference_input_size,
                dtype=dt,
                needs_gradient=False,
                name='a_ref')
    a_test = C.input_variable(shape=tuple(warmup_input_size[:-len(free_dimension_increment)] + [C.FreeDimension]*len(free_dimension_increment)),
                dtype=dt,
                needs_gradient=False,
                name='a_test')

    from cntk import convolution
    conv_op_without_free_dim = convolution(conv_map, a_ref, auto_padding=[False] + [True]*len(filter_size))
    conv_op_with_free_dim = convolution(conv_map, a_test, auto_padding=[False] + [True]*len(filter_size))

    input_img_ref = np.ones(reference_input_size, dtype=dt)
    output_ref = conv_op_without_free_dim.eval({a_ref: input_img_ref}, device=dev)

    input_img_warmup = np.ones(warmup_input_size, dtype=dt)
    _ = conv_op_with_free_dim.eval({a_test: input_img_warmup}, device=dev)
        
    output_test = conv_op_with_free_dim.eval({a_test: input_img_ref}, device=dev)

    assert np.allclose(output_test, output_ref, atol = 1e-4)

FREE_STATIC_AXES_WITH_DYNAMIC_AXIS_CONVOLUTION_DATA = [    
    # 2D convolution with two free static axes and one batch (dynamic) axis.
    ([3, 51, 71], # warmup_input_size: Defines the input size used for first run with free static axes. 3- and 4-element vector for 2D and 3D convolution, respectively.
     [10, 12],    # free_dimension_increment: Increments to the input size for the second/actual/test run. Length defines the number of free static axes.
     [3, 3],      # filter_size: kernel size for convolution. Length defines 2D or 3D convolution.
     32,          # num_output_channels
     [4, 33]      # Half-open range for random selection of of batch-sizes (for reference and warmup)
     ),        
]
# This test point exercises convolution with multiple free static axes and batch (dynamic) axis), and ensures that the result is the same as with fixed axes.
@pytest.mark.parametrize("warmup_input_size, free_dimension_increment, filter_size, num_output_channels, batch_size_range", FREE_STATIC_AXES_WITH_DYNAMIC_AXIS_CONVOLUTION_DATA)
def test_conv_free_static_and_dynamic_axes(warmup_input_size, free_dimension_increment, filter_size, num_output_channels, batch_size_range, device_id, precision):
    dt = PRECISION_TO_TYPE[precision]
    dev = cntk_device(device_id)

    np.random.seed(0)

    conv_size = tuple([num_output_channels, warmup_input_size[0]]+filter_size)
    total_size = np.prod(conv_size)
    y = np.arange(total_size, dtype=dt)
    conv_map = constant(value=y.reshape(conv_size), device=dev)

    warmup_batchsize = np.random.randint(batch_size_range[0],batch_size_range[1])
    ref_batchsize = np.random.randint(batch_size_range[0],batch_size_range[1])

    reference_input_size = tuple(warmup_input_size[:-len(free_dimension_increment)] +
                           [x+y for x,y in zip(warmup_input_size[-len(free_dimension_increment):], free_dimension_increment)])

    a_ref = C.sequence.input_variable(shape=reference_input_size,
                dtype=dt,
                needs_gradient=False,
                sequence_axis=C.Axis.new_unique_dynamic_axis('c'))
    a_test = C.sequence.input_variable(shape=tuple(warmup_input_size[:-len(free_dimension_increment)] + [C.FreeDimension]*len(free_dimension_increment)),
                dtype=dt,
                needs_gradient=False,
                sequence_axis=C.Axis.new_unique_dynamic_axis('c'))

    from cntk import convolution
    conv_op_without_free_dim = convolution(conv_map, a_ref, auto_padding=[False] + [True]*len(filter_size))
    conv_op_with_free_dim = convolution(conv_map, a_test, auto_padding=[False] + [True]*len(filter_size))
    
    input_img_ref = np.random.random((ref_batchsize,) + reference_input_size).astype(dt)
    output_ref = conv_op_without_free_dim.eval({a_ref: input_img_ref}, device=dev)

    input_img_warmup = np.random.random((warmup_batchsize,) + tuple(warmup_input_size)).astype(dt)
    _ = conv_op_with_free_dim.eval({a_test: input_img_warmup}, device=dev)
        
    output_test = conv_op_with_free_dim.eval({a_test: input_img_ref}, device=dev)

    assert np.allclose(output_test, output_ref, atol = 1e-4)
