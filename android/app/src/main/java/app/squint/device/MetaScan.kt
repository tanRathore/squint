package app.squint.device

import androidx.exifinterface.media.ExifInterface
import java.io.ByteArrayInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

data class MetaResult(val generator: String, val camera: Boolean, val c2pa: Boolean, val sourceType: String, val notes: List<String>)

object MetaScan {
    private val generators = listOf(
        "stable diffusion" to Regex("stable[\\s_-]?diffusion|sd[-_ ]?xl|automatic1111|comfyui|invokeai|novelai"),
        "midjourney" to Regex("midjourney"),
        "dall-e" to Regex("dall[\\s·.-]?e|openai"),
        "adobe firefly" to Regex("firefly|adobe\\s+generative|generative\\s+fill"),
        "google imagen" to Regex("imagen|gemini|synthid|nano\\s*banana"),
        "flux" to Regex("black[\\s-]?forest[\\s-]?labs|\\bflux\\b"),
        "ideogram" to Regex("ideogram"),
        "leonardo" to Regex("leonardo\\.ai"),
    )
    private val cameras = Regex("apple|samsung|google|sony|canon|nikon|leica|fujifilm|olympus|panasonic|xiaomi|oneplus|huawei|motorola|nothing|ricoh|hasselblad|dji|gopro")

    fun scan(data: ByteArray): MetaResult {
        val notes = mutableListOf<String>()
        var hay = StringBuilder()
        var software = ""
        var make = ""
        var c2pa = false
        var sourceType = ""
        if (data.size > 8 && data[0] == 0x89.toByte() && data[1] == 'P'.code.toByte()) {
            for ((kind, body) in pngChunks(data)) {
                if (kind == "tEXt" || kind == "iTXt" || kind == "zTXt") {
                    val key = String(body.takeWhile { it != 0.toByte() }.toByteArray(), Charsets.ISO_8859_1)
                    val text = if (kind == "tEXt") String(body, Charsets.ISO_8859_1) else key
                    hay.append(key.lowercase()).append('=').append(text.lowercase()).append(' ')
                    if (key.lowercase() in setOf("parameters", "prompt", "workflow", "sd-metadata", "invokeai_metadata")) {
                        notes.add("png carries a generation prompt block")
                        if (software.isEmpty()) software = "stable diffusion family"
                    }
                }
                if (kind == "caBX" || String(body.take(64).toByteArray(), Charsets.ISO_8859_1).contains("c2pa")) c2pa = true
            }
        } else if (data.size > 4 && data[0] == 0xFF.toByte() && data[1] == 0xD8.toByte()) {
            try {
                val exif = ExifInterface(ByteArrayInputStream(data))
                software = exif.getAttribute(ExifInterface.TAG_SOFTWARE) ?: ""
                make = exif.getAttribute(ExifInterface.TAG_MAKE) ?: ""
                hay.append(software.lowercase()).append(' ').append(make.lowercase()).append(' ')
                hay.append((exif.getAttribute(ExifInterface.TAG_IMAGE_DESCRIPTION) ?: "").lowercase()).append(' ')
                hay.append((exif.getAttribute(ExifInterface.TAG_USER_COMMENT) ?: "").lowercase()).append(' ')
            } catch (e: Exception) {
            }
            for (seg in jpegSegments(data)) {
                val head = String(seg.take(200).toByteArray(), Charsets.ISO_8859_1).lowercase()
                if (head.contains("c2pa") || head.contains("jumb")) {
                    c2pa = true
                    hay.append(String(seg, Charsets.ISO_8859_1).lowercase()).append(' ')
                }
                if (head.contains("ns.adobe.com/xap")) {
                    val xmp = String(seg, Charsets.ISO_8859_1).lowercase()
                    hay.append(xmp).append(' ')
                    if (xmp.contains("trainedalgorithmicmedia")) sourceType = "trainedalgorithmicmedia"
                    else if (xmp.contains("digitalcapture")) sourceType = "digitalcapture"
                }
            }
        }
        val all = hay.toString()
        if (all.contains("c2pa.created") || all.contains("c2pa.actions")) c2pa = true
        if (all.contains("trainedalgorithmicmedia")) sourceType = "trainedalgorithmicmedia"
        val generator = generators.firstOrNull { it.second.containsMatchIn(all) }?.first ?: ""
        val camera = cameras.containsMatchIn(make.lowercase()) || cameras.containsMatchIn(software.lowercase())
        if (generator.isNotEmpty()) notes.add("metadata names $generator")
        if (sourceType == "trainedalgorithmicmedia") notes.add("iptc digital source type says trained algorithmic media")
        if (c2pa) notes.add("content credentials manifest present")
        if (sourceType == "digitalcapture") notes.add("iptc digital source type says camera capture")
        return MetaResult(generator, camera, c2pa, sourceType, notes)
    }

    private fun pngChunks(data: ByteArray): List<Pair<String, ByteArray>> {
        val out = mutableListOf<Pair<String, ByteArray>>()
        var pos = 8
        val bb = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN)
        while (pos + 8 <= data.size) {
            val len = bb.getInt(pos)
            if (len < 0 || pos + 12 + len > data.size) break
            val kind = String(data, pos + 4, 4, Charsets.ISO_8859_1)
            out.add(kind to data.copyOfRange(pos + 8, pos + 8 + len))
            pos += 12 + len
            if (kind == "IEND") break
        }
        return out
    }

    private fun jpegSegments(data: ByteArray): List<ByteArray> {
        val out = mutableListOf<ByteArray>()
        var pos = 2
        while (pos + 4 <= data.size) {
            if (data[pos] != 0xFF.toByte()) { pos++; continue }
            val marker = data[pos + 1].toInt() and 0xFF
            if (marker == 0xD8 || marker == 0x01 || marker in 0xD0..0xD7) { pos += 2; continue }
            if (marker == 0xDA || marker == 0xD9) break
            val len = ((data[pos + 2].toInt() and 0xFF) shl 8) or (data[pos + 3].toInt() and 0xFF)
            if (len < 2 || pos + 2 + len > data.size) break
            if (marker == 0xE1 || marker == 0xEB || marker == 0xFE) out.add(data.copyOfRange(pos + 4, pos + 2 + len))
            pos += 2 + len
        }
        return out
    }
}
