package app.squint.device

import android.graphics.Bitmap
import app.squint.LocalScorer
import app.squint.Verdict
import java.io.ByteArrayOutputStream
import java.util.UUID

object Offline {
    private val lines = mapOf(
        "en" to mapOf("likely_synthetic" to "Likely AI.", "leaning_synthetic" to "Leaning AI, not certain.", "unclear" to "Can't tell from this.", "leaning_human" to "No strong AI signals.", "verified_capture" to "Camera verified by content credentials.", "device_only" to "Checked on the phone only, no connection.", "metadata" to "The file itself says it was generated."),
        "es" to mapOf("likely_synthetic" to "Probablemente hecho con IA.", "leaning_synthetic" to "Parece IA, sin certeza.", "unclear" to "No se puede saber con esto.", "leaning_human" to "Sin señales fuertes de IA.", "verified_capture" to "Cámara verificada por credenciales de contenido.", "device_only" to "Revisado solo en el teléfono, sin conexión.", "metadata" to "El propio archivo dice que fue generado."),
        "pt" to mapOf("likely_synthetic" to "Provavelmente feito por IA.", "leaning_synthetic" to "Parece IA, sem certeza.", "unclear" to "Não dá para saber com isso.", "leaning_human" to "Sem sinais fortes de IA.", "verified_capture" to "Câmera verificada por credenciais de conteúdo.", "device_only" to "Verificado só no celular, sem conexão.", "metadata" to "O próprio arquivo diz que foi gerado."),
        "hi" to mapOf("likely_synthetic" to "शायद AI से बना है।", "leaning_synthetic" to "AI लगता है, पक्का नहीं।", "unclear" to "इससे बताना मुश्किल है।", "leaning_human" to "AI के कोई पक्के संकेत नहीं।", "verified_capture" to "कैमरे से लिया गया, कंटेंट क्रेडेंशियल से सत्यापित।", "device_only" to "सिर्फ़ फ़ोन पर जांचा गया, कनेक्शन नहीं था।", "metadata" to "फ़ाइल खुद कहती है कि यह जनरेट की गई है।"),
    )
    private val headlines = mapOf("likely_synthetic" to "Likely AI-made", "leaning_synthetic" to "Leaning AI, not certain", "unclear" to "Can't tell from this", "leaning_human" to "No strong AI signals", "verified_capture" to "Camera-verified capture")
    private val haptics = mapOf(
        "likely_synthetic" to (longArrayOf(0, 650) to intArrayOf(0, 255)),
        "leaning_synthetic" to (longArrayOf(0, 420, 110, 110) to intArrayOf(0, 255, 0, 170)),
        "unclear" to (longArrayOf(0, 70, 70, 70, 70, 70) to intArrayOf(0, 200, 0, 200, 0, 200)),
        "leaning_human" to (longArrayOf(0, 110, 110, 110) to intArrayOf(0, 160, 0, 160)),
        "verified_capture" to (longArrayOf(0, 90, 80, 380) to intArrayOf(0, 140, 0, 255)),
    )

    fun verdict(bmp: Bitmap?, original: ByteArray?, scorer: LocalScorer, lang: String, phash: String): Verdict {
        val l = lines[lang] ?: lines["en"]!!
        val evidence = mutableListOf<String>()
        var tier = "unclear"
        var p = 0.5
        val meta = original?.let { MetaScan.scan(it) }
        if (meta != null && (meta.generator.isNotEmpty() || meta.sourceType == "trainedalgorithmicmedia")) {
            tier = "likely_synthetic"; p = 0.95
            evidence.addAll(meta.notes)
        } else if (meta != null && meta.c2pa && (meta.camera || meta.sourceType == "digitalcapture")) {
            tier = "verified_capture"; p = 0.05
            evidence.add("content credentials from a camera capture")
        } else if (bmp != null) {
            val s = scorer.score(bmp)
            if (s != null) {
                p = s.toDouble()
                evidence.add("on-device model: ${(s * 100).toInt()}% synthetic")
                tier = when {
                    s >= 0.85f -> "likely_synthetic"
                    s >= 0.65f -> "leaning_synthetic"
                    s <= 0.2f -> "leaning_human"
                    else -> "unclear"
                }
            }
        }
        val say = buildString {
            append(l[tier] ?: l["unclear"])
            if (tier == "likely_synthetic" && meta != null && meta.generator.isNotEmpty()) append(' ').append(l["metadata"])
            append(' ').append(l["device_only"])
        }
        val (pat, amp) = haptics[tier] ?: haptics["unclear"]!!
        return Verdict(
            checkId = "local-" + UUID.randomUUID().toString().take(8), kind = "image", tier = tier, p = p,
            confidence = if (tier == "unclear") "low" else "medium", headline = headlines[tier] ?: "", say = say,
            pattern = pat, amplitudes = amp, evidence = evidence, seenBefore = 0, phash = phash, quick = true, decisive = true, feedbackRecorded = false,
        )
    }

    fun bytes(bmp: Bitmap): ByteArray = ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.JPEG, 85, it) }.toByteArray()
}
