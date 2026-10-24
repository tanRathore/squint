package app.squint

import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession

class SquintInteractionService : VoiceInteractionService() {

    override fun onReady() {
        super.onReady()
        live = this
    }

    override fun onShutdown() {
        if (live === this) live = null
        super.onShutdown()
    }

    fun trigger(source: String) {
        val args = Bundle().apply { putString("trigger", source) }
        showSession(args, VoiceInteractionSession.SHOW_WITH_ASSIST or VoiceInteractionSession.SHOW_WITH_SCREENSHOT)
    }

    companion object {
        @Volatile
        var live: SquintInteractionService? = null
    }
}
