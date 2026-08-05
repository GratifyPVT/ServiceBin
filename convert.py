import tensorflow as tf
import tensorflow.keras.backend as K
from keras.saving import register_keras_serializable

# ---- Custom layers (IMPORTANT: same as your model) ----
@register_keras_serializable()
class Mish(tf.keras.layers.Layer):
    def call(self, inputs):
        return inputs * K.tanh(K.softplus(inputs))

@register_keras_serializable()
class ChannelMean(tf.keras.layers.Layer):
    def call(self, x):
        return K.mean(x, axis=3, keepdims=True)

@register_keras_serializable()
class ChannelMax(tf.keras.layers.Layer):
    def call(self, x):
        return K.max(x, axis=3, keepdims=True)

# ---- Load model ----
model = tf.keras.models.load_model(
    "GarbageDetection/model/rls_mobilenetv3_mish_cbam.keras"
)

# ---- Convert ----
converter = tf.lite.TFLiteConverter.from_keras_model(model)

# 🔥 Basic conversion (start with this)
tflite_model = converter.convert()

# ---- Save ----
with open("GarbageDetection/model/model.tflite", "wb") as f:
    f.write(tflite_model)

print("Conversion done!")
