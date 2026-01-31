"""
Shim module for tf_keras.legacy_tf_layers compatibility.
tf_slim expects this module to exist for TF1-style layer APIs.
"""
from tf_keras.legacy_tf_layers.normalization import BatchNormalization, batch_normalization

__all__ = ['BatchNormalization', 'batch_normalization', 'normalization']
