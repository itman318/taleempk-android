package online.taleempk.studyhub.data

import org.junit.Assert.*
import org.junit.Test

class ChatSyncTest {
    private fun row(id:Long, body:String="hello",token:String?=null)=ChatMessage(id,1,"Me",body,"12:00",true,0,null,null,false,clientToken=token)
    @Test fun editReplacesOldVersion(){assertEquals("edited",ChatSync.merge(listOf(row(2)),MessageBatch(listOf(row(2,"edited")))).single().content)}
    @Test fun remoteDeletionAndHiddenRowsAreReconciled(){val result=ChatSync.merge(listOf(row(2),row(3)),MessageBatch(listOf(row(2).copy(deleted=true)),setOf(3)));assertEquals(1,result.size);assertTrue(result.single().deleted)}
    @Test fun acknowledgementReplacesPendingWithoutDuplicate(){val result=ChatSync.merge(listOf(row(-1,token="a")),MessageBatch(listOf(row(9,token="a"))));assertEquals(listOf(9L),result.map{it.id})}
    @Test fun parallelPendingMessagesSurviveRefresh(){val result=ChatSync.merge(listOf(row(2),row(-1,token="a"),row(-2,token="b")),MessageBatch(listOf(row(3,token="a"))));assertEquals(listOf(2L,3L,-2L),result.map{it.id})}
    @Test fun oldHistoryPrecedesCurrentMessages(){assertEquals(listOf(1L,2L,3L),ChatSync.merge(listOf(row(3)),MessageBatch(listOf(row(2),row(1)))).map{it.id})}
    @Test fun repeatedPageDoesNotDuplicateMessages(){assertEquals(1,ChatSync.merge(listOf(row(3)),MessageBatch(listOf(row(3)))).size)}
    @Test fun failedDraftSurvivesEmptyPoll(){assertTrue(ChatSync.merge(listOf(row(-1).copy(failed=true)),MessageBatch(emptyList())).single().failed)}
}
