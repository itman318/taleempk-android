package online.taleempk.studyhub.data

/** Server rows replace older versions. Local sends keep their place until acknowledged. */
object ChatSync {
    fun merge(current: List<ChatMessage>, batch: MessageBatch): List<ChatMessage> {
        val tokens = batch.messages.mapNotNull { it.clientToken }.toSet()
        val rows = current.filterNot { it.id in batch.hiddenIds || (it.id < 0 && it.clientToken in tokens) }
            .associateBy { it.id }.toMutableMap()
        batch.messages.filterNot { it.id in batch.hiddenIds }.forEach { rows[it.id] = it }
        return rows.values.filter { it.id > 0 }.sortedBy { it.id } + rows.values.filter { it.id < 0 }
    }
}
