package app.squint.device

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.util.zip.CRC32

class MetaScanTest {
    private fun chunk(kind: String, body: ByteArray): ByteArray {
        val crc = CRC32().apply { update(kind.toByteArray(Charsets.ISO_8859_1)); update(body) }
        return ByteBuffer.allocate(12 + body.size).putInt(body.size).put(kind.toByteArray(Charsets.ISO_8859_1)).put(body).putInt(crc.value.toInt()).array()
    }

    private fun png(vararg texts: Pair<String, String>): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(0x89.toByte(), 'P'.code.toByte(), 'N'.code.toByte(), 'G'.code.toByte(), 13, 10, 26, 10))
        out.write(chunk("IHDR", ByteBuffer.allocate(13).putInt(2).putInt(2).put(8).put(2).put(0).put(0).put(0).array()))
        for ((k, v) in texts) out.write(chunk("tEXt", (k + "\u0000" + v).toByteArray(Charsets.ISO_8859_1)))
        out.write(chunk("IDAT", ByteArray(4)))
        out.write(chunk("IEND", ByteArray(0)))
        return out.toByteArray()
    }

    private fun jpegWith(marker: Int, payload: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(0xFF.toByte(), 0xD8.toByte()))
        out.write(byteArrayOf(0xFF.toByte(), marker.toByte(), ((payload.size + 2) shr 8).toByte(), ((payload.size + 2) and 0xFF).toByte()))
        out.write(payload)
        out.write(byteArrayOf(0xFF.toByte(), 0xDA.toByte(), 0, 2, 0, 0, 0xFF.toByte(), 0xD9.toByte()))
        return out.toByteArray()
    }

    @Test
    fun aStableDiffusionPngIsNamed() {
        val r = MetaScan.scan(png("parameters" to "snow leopard, Steps: 30, Sampler: DPM++ 2M Karras, Model: sd_xl_base_1.0"))
        assertEquals("stable diffusion", r.generator)
        assertFalse(r.camera)
        assertTrue(r.notes.any { it.contains("prompt block") })
    }

    @Test
    fun aComfyWorkflowCountsEvenWithoutAModelName() {
        val r = MetaScan.scan(png("workflow" to "{\"nodes\": []}", "prompt" to "{}"))
        assertTrue(r.notes.any { it.contains("prompt block") })
    }

    @Test
    fun plainPngsAreLeftAlone() {
        val r = MetaScan.scan(png("Comment" to "exported from a drawing app"))
        assertEquals("", r.generator)
        assertFalse(r.c2pa)
        assertTrue(r.notes.isEmpty())
    }

    @Test
    fun iptcTrainedAlgorithmicMediaIsPickedUpFromXmp() {
        val xmp = "http://ns.adobe.com/xap/1.0/\u0000<x:xmpmeta><rdf:Description Iptc4xmpExt:DigitalSourceType=\"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia\"/></x:xmpmeta>"
        val r = MetaScan.scan(jpegWith(0xE1, xmp.toByteArray(Charsets.ISO_8859_1)))
        assertEquals("trainedalgorithmicmedia", r.sourceType)
        assertTrue(r.notes.any { it.contains("trained algorithmic media") })
    }

    @Test
    fun contentCredentialsAreNoticed() {
        val jumbf = "jumb".toByteArray() + ByteArray(8) + "c2pa.actions".toByteArray()
        val r = MetaScan.scan(jpegWith(0xEB, jumbf))
        assertTrue(r.c2pa)
    }

    @Test
    fun garbageDoesNotThrow() {
        val r = MetaScan.scan(byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE1.toByte(), 0x7F, 0x7F, 1))
        assertEquals("", r.generator)
        assertEquals(MetaResult("", false, false, "", emptyList()), MetaScan.scan(ByteArray(0)))
    }
}
