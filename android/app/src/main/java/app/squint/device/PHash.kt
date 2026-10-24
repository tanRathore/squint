package app.squint.device

import android.graphics.Bitmap
import android.graphics.Color
import kotlin.math.cos
import kotlin.math.sqrt

object PHash {
    private const val N = 32
    private val cosTable = Array(N) { u -> DoubleArray(N) { x -> cos((2 * x + 1) * u * Math.PI / (2 * N)) } }

    fun of(bmp: Bitmap): String {
        val small = Bitmap.createScaledBitmap(bmp, N, N, true)
        val px = IntArray(N * N)
        small.getPixels(px, 0, N, 0, 0, N, N)
        return fromGray(Array(N) { y -> DoubleArray(N) { x -> val c = px[y * N + x]; 0.299 * Color.red(c) + 0.587 * Color.green(c) + 0.114 * Color.blue(c) } })
    }

    fun fromGray(gray: Array<DoubleArray>): String {
        require(gray.size == N && gray.all { it.size == N }) { "pHash wants a ${N}x$N grey block" }
        val rows = Array(N) { y -> dct1d(gray[y]) }
        val low = Array(8) { v -> DoubleArray(8) }
        for (u in 0 until 8) {
            for (v in 0 until 8) {
                var s = 0.0
                for (y in 0 until N) s += rows[y][u] * cosTable[v][y]
                low[v][u] = s
            }
        }
        val flat = low.flatMap { it.toList() }.sorted()
        val median = (flat[31] + flat[32]) / 2
        var bits = 0L
        for (v in 0 until 8) for (u in 0 until 8) {
            bits = bits shl 1
            if (low[v][u] > median) bits = bits or 1L
        }
        return String.format("%016x", bits)
    }

    private fun dct1d(x: DoubleArray): DoubleArray {
        val out = DoubleArray(N)
        for (u in 0 until N) {
            var s = 0.0
            for (i in 0 until N) s += x[i] * cosTable[u][i]
            out[u] = s
        }
        return out
    }

    fun distance(a: String, b: String): Int {
        if (a.length != 16 || b.length != 16) return 64
        return java.lang.Long.bitCount(java.lang.Long.parseUnsignedLong(a, 16) xor java.lang.Long.parseUnsignedLong(b, 16))
    }
}
