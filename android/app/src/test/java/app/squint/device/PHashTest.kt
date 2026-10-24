package app.squint.device

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PHashTest {
    private fun lcg(seed: Long): Iterator<Long> = iterator {
        var s = seed and 0xFFFFFFFFL
        while (true) {
            s = (1103515245L * s + 12345L) and 0x7FFFFFFFL
            yield(s shr 16)
        }
    }

    private fun grid(f: (Int, Int) -> Int) = Array(32) { y -> DoubleArray(32) { x -> f(x, y).toDouble() } }

    @Test
    fun matchesTheServerOnARamp() {
        assertEquals("8c3585376ee22d5a", PHash.fromGray(grid { x, y -> (x * 7 + y * 13) % 256 }))
    }

    @Test
    fun matchesTheServerOnACheckerboard() {
        assertEquals("fd55f554550000ff", PHash.fromGray(grid { x, y -> ((x / 3 + y / 5) % 2) * 180 + 30 }))
    }

    @Test
    fun matchesTheServerOnNoise() {
        val r = lcg(42)
        val g = Array(32) { DoubleArray(32) { (r.next() % 256).toDouble() } }
        assertEquals("ec9da8b74e90a89a", PHash.fromGray(g))
    }

    @Test
    fun matchesTheServerOnRingsWithNoise() {
        val r = lcg(7)
        val g = Array(32) { y -> DoubleArray(32) { x -> (((x * x + 3 * y * y) % 251 + (r.next() % 21).toInt()) % 256).toDouble() } }
        assertEquals("8e0f0f2e060ebc7e", PHash.fromGray(g))
    }

    @Test
    fun smallBrightnessChangesBarelyMoveTheHash() {
        val base = grid { x, y -> (x * 7 + y * 13) % 256 }
        val brighter = Array(32) { y -> DoubleArray(32) { x -> minOf(255.0, base[y][x] * 1.08 + 6) } }
        assertTrue(PHash.distance(PHash.fromGray(base), PHash.fromGray(brighter)) <= 4)
    }

    @Test
    fun distanceIsHammingOverSixtyFourBits() {
        assertEquals(0, PHash.distance("8c3585376ee22d5a", "8c3585376ee22d5a"))
        assertEquals(1, PHash.distance("8c3585376ee22d5a", "8c3585376ee22d5b"))
        assertEquals(64, PHash.distance("0000000000000000", "ffffffffffffffff"))
        assertEquals(64, PHash.distance("short", "8c3585376ee22d5a"))
    }
}
