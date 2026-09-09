package online.taleempk.studyhub.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun NotificationScreen(vm:AppViewModel){
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
        item{Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
            Column(Modifier.weight(1f)){Text("Your activity",fontSize=23.sp,fontWeight=FontWeight.Bold)
                Text("${vm.notificationUnread} unread updates",color=Color(0xFF667085),fontSize=12.sp)}
            TextButton({vm.readNotification(null)},enabled=vm.notificationUnread>0){Text("Read all")}
        }}
        if(vm.notificationLoading && vm.notifications.isEmpty())item{LinearProgressIndicator(Modifier.fillMaxWidth())}
        if(!vm.notificationLoading && vm.notifications.isEmpty())item{
            Column(Modifier.fillMaxWidth().padding(vertical=60.dp),horizontalAlignment=Alignment.CenterHorizontally){
                Icon(Icons.Default.NotificationsNone,null,Modifier.size(48.dp),tint=Color(0xFF14966B))
                Spacer(Modifier.height(12.dp));Text("You're all caught up",fontWeight=FontWeight.Bold)
                Text("New replies and community updates appear here.",fontSize=12.sp,color=Color(0xFF667085))
            }
        }
        items(vm.notifications,key={it.id}){n->
            Surface(Modifier.fillMaxWidth().clickable{vm.readNotification(n)},shape=RoundedCornerShape(18.dp),
                color=if(n.read)Color.White else Color(0xFFF0F8E9)){
                Row(Modifier.padding(16.dp),verticalAlignment=Alignment.CenterVertically){
                    Icon(when(n.type){"message"->Icons.Default.ChatBubbleOutline;"like","react"->Icons.Default.FavoriteBorder;else->Icons.Default.NotificationsNone},null,tint=Color(0xFF14966B))
                    Spacer(Modifier.width(12.dp));Column(Modifier.weight(1f)){
                        Text(n.message,fontWeight=if(n.read)FontWeight.Normal else FontWeight.SemiBold,fontSize=14.sp,lineHeight=20.sp)
                        Spacer(Modifier.height(4.dp));Text(n.time,fontSize=11.sp,color=Color(0xFF667085))
                    }
                    if(!n.read)Icon(Icons.Default.Circle,"Unread",Modifier.padding(start=6.dp).size(8.dp),tint=Color(0xFF14966B))
                }
            }
        }
    }
}
