package app.squint

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import kotlin.math.PI
import kotlin.math.min
import kotlin.math.sin

class Earcons {
    private val rate = 22050

    private fun tone(freq: Double, ms: Int, gain: Float = 0.5f): ShortArray {
        val n = rate * ms / 1000
        val out = ShortArray(n)
        val fade = min(n / 6, rate / 50)
        for (i in 0 until n) {
            val env = when {
                i < fade -> i.toFloat() / fade
                i > n - fade -> (n - i).toFloat() / fade
                else -> 1f
            }
            out[i] = (sin(2 * PI * freq * i / rate) * Short.MAX_VALUE * gain * env).toInt().toShort()
        }
        return out
    }

    private fun silence(ms: Int) = ShortArray(rate * ms / 1000)

    fun play(pattern: LongArray, amplitudes: IntArray) {
        if (pattern.isEmpty()) return
        val parts = mutableListOf<ShortArray>()
        val long = pattern.any { it >= 400 }
        for (i in pattern.indices) {
            val ms = pattern[i].toInt()
            val amp = amplitudes.getOrElse(i) { 0 }
            if (amp <= 0) parts.add(silence(ms)) else parts.add(tone(if (long && ms >= 400) 392.0 else 784.0, ms, 0.25f + 0.35f * amp / 255f))
        }
        val total = parts.sumOf { it.size }
        val pcm = ShortArray(total)
        var pos = 0
        for (p in parts) { p.copyInto(pcm, pos); pos += p.size }
        try {
            val track = AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
                .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(rate).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setBufferSizeInBytes(pcm.size * 2)
                .setTransferMode(AudioTrack.MODE_STATIC)
                .build()
            track.write(pcm, 0, pcm.size)
            track.setNotificationMarkerPosition(pcm.size)
            track.setPlaybackPositionUpdateListener(object : AudioTrack.OnPlaybackPositionUpdateListener {
                override fun onMarkerReached(t: AudioTrack?) { t?.release() }
                override fun onPeriodicNotification(t: AudioTrack?) {}
            })
            track.play()
        } catch (e: Exception) {
        }
    }
}
