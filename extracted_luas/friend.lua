WND_FRIEND = 0
WND_FRIEND_X = -1
WND_FRIEND_Y = -1
WND_FRIEND_BUTTON = 0
WND_CHATROOM = 0
WND_CHATROOM_MIN = 0

function OnFriend_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnFriendInvite(dwID, dwCmdID, dwParam, pParam)
  WND_FRIEND_BUTTON = window.create(2351, window.parent(dwID), 0, 0)
  window.moveoffset(WND_FRIEND_BUTTON, window.width(WND_FRIEND) / 2 - 79, window.height(WND_FRIEND) / 2 - 46)
  return 1
end

function OnFriendInviteEx(dwID, dwCmdID, dwParam, pParam)
  game.friendinviteex()
  return 1
end

function OnFriendInvite_OK(dwID, dwCmdID, dwParam, pParam)
  game.friendinvite(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnFriendAccept_OK(dwID, dwCmdID, dwParam, pParam)
  game.friendaccept()
  return 1
end

function OnFriendAccept_Cancel(dwID, dwCmdID, dwParam, pParam)
  game.friendcancel()
  return 1
end

function OnStatusSelect(dwID, dwCmdID, dwParam, pParam)
  game.statuschange(dwParam, window.parent(window.parent(dwID)))
  window.destroy(window.parent(dwID))
  return 1
end

function OnStatusChange(dwID, dwCmdID, dwParam, pParam)
  WND_FRIEND_BUTTON = window.create(2334, window.parent(dwID), 0, 0)
  local list = window.find(WND_FRIEND_BUTTON, 2335)
  window.insertitemstr(list, game.getstring(301), 2331)
  window.insertitemstr(list, game.getstring(302), 2332)
  window.insertitemstr(list, game.getstring(303), 2333)
  window.insertitemstr(list, game.getstring(304), 2334)
  window.insertitemstr(list, game.getstring(305), 2335)
  window.insertitemstr(list, game.getstring(306), 2336)
  window.insertitemstr(list, game.getstring(307), 2337)
  window.insertitemstr(list, game.getstring(308), 2338)
  window.insertitemstr(list, game.getstring(309), 2339)
  window.insertitemstr(list, game.getstring(310), 2340)
  return 1
end

function OnFriendSay(dwID, dwCmdID, dwParam, pParam)
  game.friendsay(window.parent(dwID))
  return 1
end

function OnFriendMessage(dwID, dwCmdID, dwParam, pParam)
  game.friendmessage()
  return 1
end

function OnFriendRemove(dwID, dwCmdID, dwParam, pParam)
  game.friendremove(window.parent(dwID), window.width(WND_FRIEND), window.height(WND_FRIEND))
  return 1
end

function OnFriendRemove_OK(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.friendremoveok()
  return 1
end

function OnFriendOption(dwID, dwCmdID, dwParam, pParam)
  local w, t
  CHAT_CLICK_NAME = game.getfriendoptionname(dwID, dwParam)
  if CHAT_CLICK_NAME ~= "NULL" then
    w = window.create(2389, 0, 0, SYSTEM_HANDLER)
    t = window.find(w, 2390)
    window.settitle(t, CHAT_CLICK_NAME)
    local x, y = window.getcursorpos()
    window.limitmove(w, x, y)
    if 0 < game.getpartnernum() then
      if GROUP_DROPITEM_TYPE == 0 then
        window.enable(window.find(w, 2393), false)
      else
        window.enable(window.find(w, 2392), false)
      end
    end
  end
  return 1
end

function OnFGroupAdd(dwID, dwCmdID, dwParam, pParam)
  game.fgroupadd(window.parent(dwID), window.width(WND_FRIEND), window.height(WND_FRIEND))
  return 1
end

function OnFGroupAdd_OK(dwID, dwCmdID, dwParam, pParam)
  game.fgroupaddok(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnFGroupRemove(dwID, dwCmdID, dwParam, pParam)
  game.fgroupremove(window.parent(dwID), window.width(WND_FRIEND), window.height(WND_FRIEND))
  return 1
end

function OnFGroupRemove_OK(dwID, dwCmdID, dwParam, pParam)
  game.fgroupremoveok()
  window.destroy(window.parent(dwID))
  return 1
end

function OnFGroupName(dwID, dwCmdID, dwParam, pParam)
  game.fgroupname(window.parent(dwID), window.width(WND_FRIEND), window.height(WND_FRIEND))
  return 1
end

function OnFGroupName_OK(dwID, dwCmdID, dwParam, pParam)
  game.fgroupnameok(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnFGroupChange(dwID, dwCmdID, dwParam, pParam)
  game.fgroupchange(window.parent(dwID), window.width(WND_FRIEND), window.height(WND_FRIEND))
  return 1
end

function OnFGroupList(dwID, dwCmdID, dwParam, pParam)
  game.fgrouplist(window.parent(dwID))
  return 1
end

function OnFGroupSelect(dwID, dwCmdID, dwParam, pParam)
  game.fgroupselect(dwParam, window.parent(window.parent(dwID)))
  window.destroy(window.parent(dwID))
  return 1
end

function OnFGroupChange_OK(dwID, dwCmdID, dwParam, pParam)
  game.fgroupchangeok(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnBlackListAdd(dwID, dwCmdID, dwParam, pParam)
  game.blacklistadd(window.parent(dwID), window.width(WND_FRIEND), window.height(WND_FRIEND))
  return 1
end

function OnBlackListAdd_OK(dwID, dwCmdID, dwParam, pParam)
  game.blacklistaddok()
  window.destroy(window.parent(dwID))
  return 1
end

function OnBlackListRemove(dwID, dwCmdID, dwParam, pParam)
  game.blacklistremove(window.parent(dwID), window.width(WND_FRIEND), window.height(WND_FRIEND))
  return 1
end

function OnBlackListRemove_OK(dwID, dwCmdID, dwParam, pParam)
  game.blacklistremoveok()
  window.destroy(window.parent(dwID))
  return 1
end

function OnBlackListPrevious1(dwID, dwCmdID, dwParam, pParam)
  game.blacklistprevious1(window.parent(dwID))
  return 1
end

function OnBlackListNext1(dwID, dwCmdID, dwParam, pParam)
  game.blacklistnext1(window.parent(dwID))
  return 1
end

function OnBlackListPrevious2(dwID, dwCmdID, dwParam, pParam)
  game.blacklistprevious2(window.parent(dwID))
  return 1
end

function OnBlackListNext2(dwID, dwCmdID, dwParam, pParam)
  game.blacklistnext2(window.parent(dwID))
  return 1
end

function OnGroupModel(dwID, dwCmdID, dwParam, pParam)
  game.fgroupmodel(dwID)
  return 1
end

function OnFriendCheck(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  if appdata == 2319 then
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 2320), false)
    window.setcheck(window.find(window.parent(dwID), 2321), false)
    window.setcheck(window.find(window.parent(dwID), 1200), false)
    window.setcheck(window.find(window.parent(dwID), 12230), false)
    window.show(window.find(window.parent(dwID), 2302), true)
    window.show(window.find(window.parent(dwID), 2303), false)
    window.show(window.find(window.parent(dwID), 3201), false)
    window.show(window.find(window.parent(dwID), 1202), false)
    window.show(window.find(window.parent(dwID), 12232), false)
  elseif appdata == 2320 then
    window.setcheck(window.find(window.parent(dwID), 2319), false)
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 2321), false)
    window.setcheck(window.find(window.parent(dwID), 1200), false)
    window.setcheck(window.find(window.parent(dwID), 12230), false)
    window.show(window.find(window.parent(dwID), 2302), false)
    window.show(window.find(window.parent(dwID), 2303), true)
    window.show(window.find(window.parent(dwID), 3201), false)
    window.show(window.find(window.parent(dwID), 1202), false)
    window.show(window.find(window.parent(dwID), 12232), false)
  elseif appdata == 2321 then
    window.setcheck(window.find(window.parent(dwID), 2319), false)
    window.setcheck(window.find(window.parent(dwID), 2320), false)
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 1200), false)
    window.setcheck(window.find(window.parent(dwID), 12230), false)
    window.show(window.find(window.parent(dwID), 2302), false)
    window.show(window.find(window.parent(dwID), 2303), false)
    window.show(window.find(window.parent(dwID), 3201), true)
    window.show(window.find(window.parent(dwID), 1202), false)
    window.show(window.find(window.parent(dwID), 12232), false)
    ChangePage(window.parent(dwID))
    game.mailcommand(0, appdata, 0, 0)
  elseif appdata == 1200 then
    window.setcheck(window.find(window.parent(dwID), 2319), false)
    window.setcheck(window.find(window.parent(dwID), 2320), false)
    window.setcheck(window.find(window.parent(dwID), 2321), false)
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 12230), false)
    window.show(window.find(window.parent(dwID), 2302), false)
    window.show(window.find(window.parent(dwID), 2303), false)
    window.show(window.find(window.parent(dwID), 3201), false)
    window.show(window.find(window.parent(dwID), 1202), true)
    window.show(window.find(window.parent(dwID), 12232), false)
  elseif appdata == 12230 then
    window.setcheck(window.find(window.parent(dwID), 2319), false)
    window.setcheck(window.find(window.parent(dwID), 2320), false)
    window.setcheck(window.find(window.parent(dwID), 2321), false)
    window.setcheck(window.find(window.parent(dwID), 1200), false)
    window.setcheck(dwID, true)
    window.show(window.find(window.parent(dwID), 2302), false)
    window.show(window.find(window.parent(dwID), 2303), false)
    window.show(window.find(window.parent(dwID), 3201), false)
    window.show(window.find(window.parent(dwID), 1202), false)
    window.show(window.find(window.parent(dwID), 12232), true)
    game.gamemenu()
    game.getstageplayers(0)
  end
  return 1
end

function CreateFriendWnd()
  if window.isexist(WND_FRIEND) then
    window.destroy(WND_FRIEND)
    WND_FRIEND = 0
    return
  end
  WND_FRIEND = window.create(2301, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_FRIEND_X or 0 > WND_FRIEND_Y then
    window.move(WND_FRIEND, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_FRIEND, WND_FRIEND_X, WND_FRIEND_Y)
  end
  window.regsetting(WND_FRIEND, "WND_FRIEND")
  window.setcheck(window.find(WND_FRIEND, 2319), true)
  game.friendwnd(WND_FRIEND)
  game.mailcommand(0, 1, 0, 0)
  game.chatroomrefresh()
end

function OnFriendClose(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_FRIEND)
  WND_FRIEND = 0
  return 1
end

function OnMessageSend(dwID, dwCmdID, dwParam, pParam)
  game.messagesend(window.parent(dwID))
  return 1
end

function OnMessageClose(dwID, dwCmdID, dwParam, pParam)
  game.messageclose(dwID)
  window.destroy(dwID)
  return 1
end

function OnMessageInvite(dwID, dwCmdID, dwParam, pParam)
  game.messageinvite(window.parent(dwID))
  return 1
end

function OnMessageChangePage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  if appdata == 2942 then
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 2943), false)
  else
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 2942), false)
  end
  return 1
end

function OnMessageInviteAdd(dwID, dwCmdID, dwParam, pParam)
  game.messageinviteadd(window.parent(dwID))
  return 1
end

function OnMessageInviteDel(dwID, dwCmdID, dwParam, pParam)
  game.messageinvitedel(window.parent(dwID))
  return 1
end

function OnMessageInviteOK(dwID, dwCmdID, dwParam, pParam)
  game.messageinviteok(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnMessageInviteCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnMessageWndMin(dwID, dwCmdID, dwParam, pParam)
  window.show(dwID, false)
  return 1
end

function OnMessageWndMax(dwID, dwCmdID, dwParam, pParam)
  window.show(window.getappdata(dwID), true)
  window.seticon(dwID, 2930)
  return 1
end

function OnChatRoomRefresh(dwID, dwCmdID, dwParam, pParam)
  game.chatroomrefresh()
  return 1
end

function OnChatRoomAddWnd(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CHATROOM) then
    return 1
  end
  window.moveoffset(window.create(1220, window.parent(dwID), 0, 0), window.width(WND_FRIEND) / 2 - 79, window.height(WND_FRIEND) / 2 - 52)
  return 1
end

function OnChatRoomJoin(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CHATROOM) then
    return 1
  end
  game.chatroomjoin()
  return 1
end

function OnChatRoomAddWnd_OK(dwID, dwCmdID, dwParam, pParam)
  game.chatroomadd()
  window.destroy(window.parent(dwID))
  return 1
end

function OnChatRoomAddWnd_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnChatRoomClose(dwID, dwCmdID, dwParam, pParam)
  game.chatroomleave()
  window.destroy(dwID)
  WND_CHATROOM = 0
  return 1
end

function OnChatRoomWndMin(dwID, dwCmdID, dwParam, pParam)
  window.show(dwID, false)
  return 1
end

function OnChatRoomWndMax(dwID, dwCmdID, dwParam, pParam)
  window.show(window.getappdata(dwID), true)
  window.seticon(dwID, 1244)
  return 1
end

function OnChatRoomSend(dwID, dwCmdID, dwParam, pParam)
  game.chatroomsend(window.parent(dwID))
  return 1
end

function OnChatRoomMaster(dwID, dwCmdID, dwParam, pParam)
  game.chatroommaster()
  return 1
end

function OnChatRoomKick(dwID, dwCmdID, dwParam, pParam)
  game.chatroomkick()
  return 1
end

function ShowPlayersSortName(dwID, dwCmdID, dwParam, pParam)
  game.getstageplayers(0)
  return 1
end

function ShowPlayersSortTitle(dwID, dwCmdID, dwParam, pParam)
  game.getstageplayers(1)
  return 1
end

function ShowPlayersSortSex(dwID, dwCmdID, dwParam, pParam)
  game.getstageplayers(2)
  return 1
end

function OnInvitePlayer(dwID, dwCmdID, dwParam, pParam)
  game.inviteplayer()
  return 1
end

function OnMinigameInviteEx(dwID, dwCmdID, dwParam, pParam)
  game.minigameinviteex()
  return 1
end
