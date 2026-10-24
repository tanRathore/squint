package app.squint.device

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Rect
import java.nio.FloatBuffer
import kotlin.math.exp

data class ScreenGuess(val rect: Rect?, val kind: String, val confidence: Float)

class ScreenModel(ctx: Context) {
    private val kinds = listOf("photo", "video", "text", "none")
    private var session: OrtSession? = null
    private var inputName = "input"
    private val env: OrtEnvironment? = try { OrtEnvironment.getEnvironment() } catch (e: Throwable) { null }

    init {
        try {
            val bytes = ctx.assets.open("screen.onnx").use { it.readBytes() }
            session = env?.createSession(bytes)
            inputName = session?.inputNames?.firstOrNull() ?: "input"
        } catch (e: Throwable) {
            session = null
        }
    }

    val available get() = session != null

    fun guess(bmp: Bitmap): ScreenGuess? {
        val s = session ?: return null
        val e = env ?: return null
        val w = 160
        val h = 320
        val small = Bitmap.createScaledBitmap(bmp, w, h, true)
        val px = IntArray(w * h)
        small.getPixels(px, 0, w, 0, 0, w, h)
        val buf = FloatBuffer.allocate(3 * w * h)
        for (c in 0 until 3) for (i in px.indices) {
            val v = when (c) { 0 -> (px[i] shr 16) and 0xff; 1 -> (px[i] shr 8) and 0xff; else -> px[i] and 0xff }
            buf.put(v / 255f)
        }
        buf.rewind()
        var tensor: OnnxTensor? = null
        var result: OrtSession.Result? = null
        try {
            tensor = OnnxTensor.createTensor(e, buf, longArrayOf(1, 3, h.toLong(), w.toLong()))
            result = s.run(mapOf(inputName to tensor))
            val box = ((result[0].value as Array<*>)[0] as FloatArray)
            val logits = ((result[1].value as Array<*>)[0] as FloatArray)
            val m = logits.max()
            val exps = logits.map { exp(it - m) }
            val sum = exps.sum()
            val k = exps.indices.maxBy { exps[it] }
            val conf = (exps[k] / sum)
            val kind = kinds[k]
            if (kind == "none") return ScreenGuess(null, kind, conf)
            val rect = Rect((box[0] * bmp.width).toInt(), (box[1] * bmp.height).toInt(), (box[2] * bmp.width).toInt(), (box[3] * bmp.height).toInt())
            return ScreenGuess(rect, kind, conf)
        } catch (t: Throwable) {
            return null
        } finally {
            result?.close()
            tensor?.close()
        }
    }
}
