package online.taleempk.studyhub.media

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.os.SystemClock
import online.taleempk.studyhub.data.VoiceClip
import java.io.File

class VoiceRecorder(private val context: Context) {
    private var recorder: MediaRecorder? = null
    private var file: File? = null
    private var startedAt = 0L

    @Suppress("DEPRECATION")
    fun start() {
        cancel()
        val output = File.createTempFile("taleempk-voice-", ".m4a", context.cacheDir)
        val next = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(context) else MediaRecorder()
        next.setAudioSource(MediaRecorder.AudioSource.MIC)
        next.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        next.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        next.setAudioEncodingBitRate(96_000)
        next.setAudioSamplingRate(48_000)
        next.setAudioChannels(1)
        next.setMaxDuration(120_000)
        next.setOutputFile(output.absolutePath)
        next.prepare()
        next.start()
        recorder = next
        file = output
        startedAt = SystemClock.elapsedRealtime()
    }

    fun stop(): VoiceClip {
        val elapsed = ((SystemClock.elapsedRealtime() - startedAt) / 1000L).toInt().coerceIn(1, 120)
        val output = requireNotNull(file)
        try { recorder?.stop() } finally { recorder?.release(); recorder = null }
        if (!output.exists() || output.length() < 256) {
            output.delete()
            throw IllegalStateException("Recording was empty.")
        }
        file = null
        return VoiceClip(output.absolutePath, elapsed)
    }

    fun cancel() {
        try { recorder?.stop() } catch (_: Exception) { }
        recorder?.release()
        recorder = null
        file?.delete()
        file = null
    }
}
