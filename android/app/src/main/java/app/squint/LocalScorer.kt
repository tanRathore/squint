package app.squint

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import java.nio.FloatBuffer
import kotlin.math.exp

class LocalScorer(ctx: Context) {
    private var session: OrtSession? = null
    private var inputName = "input"
    private val env: OrtEnvironment? = try { OrtEnvironment.getEnvironment() } catch (e: Throwable) { null }

    init {
        try {
            val bytes = ctx.assets.open("squint.onnx").use { it.readBytes() }
            session = env?.createSession(bytes)
            inputName = session?.inputNames?.firstOrNull() ?: "input"
        } catch (e: Throwable) {
            session = null
        }
    }

    val available get() = session != null

    fun score(bmp: Bitmap): Float? {
        val s = session ?: return null
        val e = env ?: return null
        val size = 224
        val scaled = centerCrop(bmp, size)
        val buf = FloatBuffer.allocate(3 * size * size)
        val px = IntArray(size * size)
        scaled.getPixels(px, 0, size, 0, 0, size, size)
        val mean = floatArrayOf(0.485f, 0.456f, 0.406f)
        val std = floatArrayOf(0.229f, 0.224f, 0.225f)
        for (c in 0 until 3) {
            for (i in px.indices) {
                val v = when (c) {
                    0 -> (px[i] shr 16) and 0xff
                    1 -> (px[i] shr 8) and 0xff
                    else -> px[i] and 0xff
                }
                buf.put(((v / 255f) - mean[c]) / std[c])
            }
        }
        buf.rewind()
        var tensor: OnnxTensor? = null
        var result: OrtSession.Result? = null
        try {
            tensor = OnnxTensor.createTensor(e, buf, longArrayOf(1, 3, size.toLong(), size.toLong()))
            result = s.run(mapOf(inputName to tensor))
            val logits = when (val arr = result[0].value) {
                is Array<*> -> arr[0] as? FloatArray
                is FloatArray -> arr
                else -> null
            } ?: return null
            return if (logits.size >= 2) {
                val m = logits.max()
                val e1 = exp(logits[1] - m)
                val e0 = exp(logits[0] - m)
                e1 / (e0 + e1)
            } else {
                1f / (1f + exp(-logits[0]))
            }
        } catch (t: Throwable) {
            return null
        } finally {
            result?.close()
            tensor?.close()
        }
    }

    private fun centerCrop(bmp: Bitmap, size: Int): Bitmap {
        val scale = size.toFloat() / minOf(bmp.width, bmp.height)
        val w = maxOf(size, (bmp.width * scale).toInt())
        val h = maxOf(size, (bmp.height * scale).toInt())
        val scaled = Bitmap.createScaledBitmap(bmp, w, h, true)
        return Bitmap.createBitmap(scaled, (w - size) / 2, (h - size) / 2, size, size)
    }
}
