package app.squint

import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

class QuickTile : TileService() {
    override fun onStartListening() {
        qsTile?.apply {
            state = if (SquintInteractionService.live != null) Tile.STATE_INACTIVE else Tile.STATE_UNAVAILABLE
            label = getString(R.string.tile_label)
            updateTile()
        }
    }

    override fun onClick() {
        val intent = Intent(this, TriggerActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (Build.VERSION.SDK_INT >= 34) {
            val pi = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            startActivityAndCollapse(pi)
        } else {
            @Suppress("DEPRECATION")
            startActivityAndCollapse(intent)
        }
    }
}
