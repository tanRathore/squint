package app.squint

import android.content.Context
import android.media.AudioAttributes
import android.os.Bundle
import android.speech.tts.TextToSpeech
import java.util.Locale

class Whisper(ctx: Context) {
    private var ready = false
    private val pending = ArrayDeque<String>()
    private val tts: TextToSpeech

    init {
        tts = TextToSpeech(ctx.applicationContext) { status -> onInit(status) }
    }

    private fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) return
        ready = true
        tts.language = Locale.getDefault()
        tts.setSpeechRate(1.05f)
        tts.setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build()
        )
        while (pending.isNotEmpty()) speakNow(pending.removeFirst())
    }

    fun say(text: String) {
        if (text.isBlank()) return
        if (!ready) {
            pending.addLast(text)
            return
        }
        speakNow(text)
    }

    private fun speakNow(text: String) {
        val params = Bundle().apply { putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 0.55f) }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, params, "squint-${System.nanoTime()}")
    }
}
