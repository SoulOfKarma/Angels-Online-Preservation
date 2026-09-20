function SetCurrentContent()
  if SYSTEM_CHANNEL_SIZE ~= 0 then
    if SYSTEM_CUR_CHANNEL == 0 then
      window.show(WND_CHAT_CONTENT_0, true)
      
      window.show(WND_CHAT_CONTENT_1, false)
      window.show(WND_CHAT_CONTENT_2, false)
      window.show(WND_CHAT_CONTENT_3, false)
    elseif SYSTEM_CUR_CHANNEL == 1 then
      window.show(WND_CHAT_CONTENT_0, false)
      window.show(WND_CHAT_CONTENT_1, true)
      window.show(WND_CHAT_CONTENT_2, false)
      window.show(WND_CHAT_CONTENT_3, false)
    elseif SYSTEM_CUR_CHANNEL == 2 then
      window.show(WND_CHAT_CONTENT_0, false)
      window.show(WND_CHAT_CONTENT_1, false)
      window.show(WND_CHAT_CONTENT_2, true)
      window.show(WND_CHAT_CONTENT_3, false)
    elseif SYSTEM_CUR_CHANNEL == 3 then
      window.show(WND_CHAT_CONTENT_0, false)
      window.show(WND_CHAT_CONTENT_1, false)
      window.show(WND_CHAT_CONTENT_2, false)
      window.show(WND_CHAT_CONTENT_3, true)
    end
  end
end

function OnSwitchChannelTab(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.find(WND_CHAT, 108)
  SYSTEM_CUR_CHANNEL = window.getradio(w)
  SetCurrentContent()
  return 1
end

function OnSwitchChannelSize(dwID, dwCmdID, dwParam, pParam)
  local n, w, l, old, old_0, old_1, old_2, old_3, m0, m1, m2, m3
  old = WND_CHAT
  old_0 = WND_CHAT_CONTENT_0
  old_1 = WND_CHAT_CONTENT_1
  old_2 = WND_CHAT_CONTENT_2
  old_3 = WND_CHAT_CONTENT_3
  WND_CHAT = 0
  window.trace("==Update OnSwitchChannelSize START==")
  SYSTEM_CHANNEL_SIZE = SYSTEM_CHANNEL_SIZE + 1
  if UseBigFont == true and SYSTEM_CHANNEL_SIZE == 1 then
    SYSTEM_CHANNEL_SIZE = 2
  end
  if SYSTEM_CHANNEL_SIZE > 3 then
    SYSTEM_CHANNEL_SIZE = 0
  end
  if SYSTEM_CHANNEL_SIZE == 0 then
    n = 152
    m0 = 230
    m1 = 231
    m2 = 232
    m3 = 233
    l = 153
  elseif SYSTEM_CHANNEL_SIZE == 1 then
    n = 101
    m0 = 129
    m1 = 234
    m2 = 235
    m3 = 236
    l = 103
  elseif SYSTEM_CHANNEL_SIZE == 3 then
    n = 143
    m0 = 150
    m1 = 237
    m2 = 238
    m3 = 239
    l = 145
  else
    n = 134
    m0 = 141
    m1 = 240
    m2 = 241
    m3 = 242
    l = 136
  end
  WND_CHAT = window.create(n, 0, 0, SYSTEM_HANDLER)
  window.move(WND_CHAT, 0, SYSTEM_SCREEN_HEIGHT - window.height(WND_CHAT) - 6)
  w = window.find(WND_CHAT, l)
  if game.isdef("__PAD_CONTROL") == false then
    window.setalwaysedit(w)
  end
  if m0 ~= 0 then
    WND_CHAT_CONTENT_0 = window.find(WND_CHAT, m0)
    local string
    if UseBigFont == true then
      string = "true"
    else
      string = "false"
    end
    window.trace("m0:" .. m0)
    window.trace("UseBigFont:" .. string)
    window.trace("SYSTEM_CHANNEL_SIZE:" .. SYSTEM_CHANNEL_SIZE)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_0, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.trace("set SYSTEM_CHANNEL_SIZE = 2 data")
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_0, 38)
        window.setworkrange(WND_CHAT_CONTENT_0, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_0, 4)
        window.setlineheight(WND_CHAT_CONTENT_0, 17)
        window.trace("set SYSTEM_CHANNEL_SIZE = 2 data OK")
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.trace("set SYSTEM_CHANNEL_SIZE = 3 data")
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_0, 38)
        window.setworkrange(WND_CHAT_CONTENT_0, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_0, 7)
        window.setlineheight(WND_CHAT_CONTENT_0, 17)
        window.trace("set SYSTEM_CHANNEL_SIZE = 3 data OK")
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_0, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_0, false)
    window.copyfrom(WND_CHAT_CONTENT_0, old_0)
  else
    WND_CHAT_CONTENT_0 = 0
  end
  if m1 ~= 0 then
    WND_CHAT_CONTENT_1 = window.find(WND_CHAT, m1)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_1, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_1, 38)
        window.setworkrange(WND_CHAT_CONTENT_1, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_1, 4)
        window.setlineheight(WND_CHAT_CONTENT_1, 17)
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_1, 38)
        window.setworkrange(WND_CHAT_CONTENT_1, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_1, 7)
        window.setlineheight(WND_CHAT_CONTENT_1, 17)
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_1, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_1, false)
    window.copyfrom(WND_CHAT_CONTENT_1, old_1)
  else
    WND_CHAT_CONTENT_1 = 0
  end
  if m2 ~= 0 then
    WND_CHAT_CONTENT_2 = window.find(WND_CHAT, m2)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_2, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_2, 38)
        window.setworkrange(WND_CHAT_CONTENT_2, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_2, 4)
        window.setlineheight(WND_CHAT_CONTENT_2, 17)
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_2, 38)
        window.setworkrange(WND_CHAT_CONTENT_2, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_2, 7)
        window.setlineheight(WND_CHAT_CONTENT_2, 17)
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_2, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_2, false)
    window.copyfrom(WND_CHAT_CONTENT_2, old_2)
  else
    WND_CHAT_CONTENT_2 = 0
  end
  if m3 ~= 0 then
    WND_CHAT_CONTENT_3 = window.find(WND_CHAT, m3)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_3, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_3, 38)
        window.setworkrange(WND_CHAT_CONTENT_3, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_3, 4)
        window.setlineheight(WND_CHAT_CONTENT_3, 17)
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_3, 38)
        window.setworkrange(WND_CHAT_CONTENT_3, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_3, 7)
        window.setlineheight(WND_CHAT_CONTENT_3, 17)
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_3, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_3, false)
    window.copyfrom(WND_CHAT_CONTENT_3, old_3)
  else
    WND_CHAT_CONTENT_3 = 0
  end
  SetCurrentContent()
  w = window.find(WND_CHAT, 108)
  window.setradio(w, SYSTEM_CUR_CHANNEL)
  SetCurSpeechIcon(1)
  window.destroy(old)
  game.updatemagicstate()
  game.setminwnd()
  window.trace("--Update OnSwitchChannelSize END--")
  return 1
end

function OnChatInput(dwID, dwCmdID, dwParam, pParam)
  if SYSTEM_CUR_CHANNEL == 0 then
    if WND_CHAT_CONTENT_0 ~= 0 then
    end
  elseif SYSTEM_CUR_CHANNEL == 1 then
    if WND_CHAT_CONTENT_1 ~= 0 then
    end
  elseif SYSTEM_CUR_CHANNEL == 2 then
    if WND_CHAT_CONTENT_2 ~= 0 then
    end
  elseif SYSTEM_CUR_CHANNEL ~= 3 or WND_CHAT_CONTENT_3 ~= 0 then
  end
  return 1
end

function OnSelectSpeech(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.create(415, 0, 0, SYSTEM_HANDLER)
  local nAddCount = 0
  if game.isdef("__MARRY") then
    window.show(window.find(w, 958), true)
    nAddCount = nAddCount + 1
  else
    window.show(window.find(w, 958), false)
  end
  if game.isdef("__BATTLEFIELD") then
    window.show(window.find(w, 490), true)
    nAddCount = nAddCount + 1
  else
    window.show(window.find(w, 490), false)
  end
  if game.isdef("__BATTLEFIELD") and game.isdef("__MARRY") == false then
    window.move(window.find(w, 490), 7, 102)
  end
  local width = 78
  if game.isdef("__KOREA") then
    width = 82
  end
  if nAddCount == 0 then
    window.setwindowsize(w, width, 107)
    window.move(w, 0, SYSTEM_SCREEN_HEIGHT - 1 - 133)
  elseif nAddCount == 1 then
    if game.isdef("__BATTLEFIELD") then
      window.move(window.find(w, 490), 7, 102)
    end
    window.setwindowsize(w, width, 127)
    window.move(w, 0, SYSTEM_SCREEN_HEIGHT - 1 - 153)
  elseif nAddCount == 2 then
    window.setwindowsize(w, width, 147)
    window.move(w, 0, SYSTEM_SCREEN_HEIGHT - 1 - 173)
  end
  return 1
end

function SetCurSpeechIcon(bNoShowMsg)
  local w, n, nMsg
  if SYSTEM_CHANNEL_SIZE == 0 then
    n = 154
  elseif SYSTEM_CHANNEL_SIZE == 1 then
    n = 104
  elseif SYSTEM_CHANNEL_SIZE == 3 then
    n = 146
  else
    n = 137
  end
  w = window.find(WND_CHAT, n)
  if w ~= 0 then
    if SYSTEM_CUR_SPEECH == 0 then
      n = 104
      nMsg = 550
    elseif SYSTEM_CUR_SPEECH == 1 then
      n = 417
      nMsg = 551
    elseif SYSTEM_CUR_SPEECH == 2 then
      n = 418
      nMsg = 552
    elseif SYSTEM_CUR_SPEECH == 3 then
      n = 419
      nMsg = 553
    elseif SYSTEM_CUR_SPEECH == 4 then
      n = 420
      nMsg = 554
    elseif SYSTEM_CUR_SPEECH == 5 then
      if game.isdef("__MARRY") and game.isdef("__BATTLEFIELD") then
        n = 958
        nMsg = 1842
      elseif game.isdef("__MARRY") then
        n = 958
        nMsg = 1842
      elseif game.isdef("__BATTLEFIELD") then
        n = 490
        nMsg = 2212
      end
    elseif SYSTEM_CUR_SPEECH == 6 and game.isdef("__MARRY") and game.isdef("__BATTLEFIELD") then
      n = 490
      nMsg = 2212
    end
    window.seticon(w, n)
    if bNoShowMsg ~= 1 then
      game.addsystemmessage(nMsg)
    end
  end
end

function OnChangeSpeech(dwID, dwCmdID, dwParam, pParam)
  if dwCmdID == 416 then
    SYSTEM_CUR_SPEECH = 0
  elseif dwCmdID == 417 then
    SYSTEM_CUR_SPEECH = 1
  elseif dwCmdID == 418 then
    SYSTEM_CUR_SPEECH = 2
  elseif dwCmdID == 419 then
    SYSTEM_CUR_SPEECH = 3
  elseif dwCmdID == 420 then
    SYSTEM_CUR_SPEECH = 4
  elseif dwCmdID == 958 then
    if game.isdef("__MARRY") then
      SYSTEM_CUR_SPEECH = 5
    end
  elseif dwCmdID == 490 and game.isdef("__BATTLEFIELD") then
    SYSTEM_CUR_SPEECH = 6
  end
  SetCurSpeechIcon()
  window.destroy(window.parent(dwID))
  return 1
end

function OnSetupFilter(dwID, dwCmdID, dwParam, pParam)
  local wnd
  if game.isdef("__TELL_FILTER") then
    wnd = window.create(12270, 0, 0, SYSTEM_HANDLER)
    window.move(wnd, 280, SYSTEM_SCREEN_HEIGHT - 1 - 194)
  else
    wnd = window.create(421, 0, 0, SYSTEM_HANDLER)
    window.move(wnd, 280, SYSTEM_SCREEN_HEIGHT - 1 - 140)
  end
  game.initchfilter(wnd)
  return 1
end

function OnUpdateChFilter(dwID, dwCmdID, dwParam, pParam)
  game.updatechfilter(window.parent(dwID))
  return 1
end

function OnShowTellList(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.create(431, 0, 0, SYSTEM_HANDLER)
  window.move(w, 302, SYSTEM_SCREEN_HEIGHT - 1 - 110)
  w = window.find(w, 432)
  game.updatetelllist(w)
  return 1
end

function GetChatInputWindow()
  local w, l
  if SYSTEM_CHANNEL_SIZE == 0 then
    l = 153
  elseif SYSTEM_CHANNEL_SIZE == 1 then
    l = 103
  elseif SYSTEM_CHANNEL_SIZE == 3 then
    l = 145
  else
    l = 136
  end
  w = window.find(WND_CHAT, l)
  return w
end

function SetTell(strName)
  local w
  w = GetChatInputWindow()
  window.settitle(w, "\"" .. strName .. " ")
  if game.isdef("PS3") == true then
    window.setfocus(w)
    game.openinputtext(w)
  end
end

function OnClickTellList(dwID, dwCmdID, dwParam, pParam)
  SetTell(window.getitemtitle(dwID, dwParam))
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatTell(dwID, dwCmdID, dwParam, pParam)
  local str, w
  if pParam ~= 0 then
    SetTell(window.getbufferstring(pParam))
  end
  return 1
end

CHAT_CLICK_NAME = ""
local dwNetID = 0

function OnClickChatOption(dwID, dwCmdID, dwParam, pParam)
  local w, t, nRow
  if pParam ~= 0 then
    local x, y = window.getcursorpos()
    CHAT_CLICK_NAME = window.getbufferstring(pParam)
    w = window.create(565, 0, 0, SYSTEM_HANDLER)
    t = window.find(w, 566)
    window.settitle(t, CHAT_CLICK_NAME)
    window.limitmove(w, x, y)
    if 0 < game.getpartnernum() then
      if GROUP_DROPITEM_TYPE == 0 then
        window.enable(window.find(w, 569), false)
      else
        window.enable(window.find(w, 568), false)
      end
    end
    nRow = 5
    if dwID ~= 0 then
      window.show(window.find(w, 685), false)
      window.show(window.find(w, 14699), false)
      window.show(window.find(w, 2469), false)
    else
      local hWnd = window.find(w, 685)
      window.show(hWnd, true)
      window.move(hWnd, window.left(hWnd), window.top(w) + 31 + nRow * 16)
      nRow = nRow + 1
      if game.isdef("__CARD") == true then
        hWnd = window.find(w, 14699)
        window.show(hWnd, true)
        window.move(hWnd, window.left(hWnd), window.top(w) + 31 + nRow * 16)
        nRow = nRow + 1
      else
        window.show(window.find(w, 14699), false)
      end
      if game.isdef("__EQUIPVIEW") == true then
        hWnd = window.find(w, 2469)
        window.show(hWnd, true)
        window.move(hWnd, window.left(hWnd), window.top(w) + 31 + nRow * 16)
        nRow = nRow + 1
      else
        window.show(window.find(w, 2469), false)
      end
    end
    window.setwindowsize(w, 110, 34 + nRow * 16)
    dwNetID = dwParam
  end
  return 1
end

function OnClickChatOptionTell(dwID, dwCmdID, dwParam, pParam)
  SetTell(CHAT_CLICK_NAME)
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatOptionParty1(dwID, dwCmdID, dwParam, pParam)
  game.groupinvite(CHAT_CLICK_NAME, 0)
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatOptionParty2(dwID, dwCmdID, dwParam, pParam)
  game.groupinvite(CHAT_CLICK_NAME, 1)
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatOptionFriend(dwID, dwCmdID, dwParam, pParam)
  game.friendinvitebyname(CHAT_CLICK_NAME)
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatOptionGuild(dwID, dwCmdID, dwParam, pParam)
  game.guildinvite(CHAT_CLICK_NAME)
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatOptionTrade(dwID, dwCmdID, dwParam, pParam)
  game.tradeinviteex(dwNetID)
  dwNetID = 0
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatOptionViewCardBook(dwID, dwCmdID, dwParam, pParam)
  game.viewotherplayercardbook(dwNetID, CHAT_CLICK_NAME)
  dwNetID = 0
  window.destroy(window.parent(dwID))
  return 1
end

function OnClickChatOptionViewEquip(dwID, dwCmdID, dwParam, pParam)
  game.viewotherplayerequip(dwNetID)
  dwNetID = 0
  window.destroy(window.parent(dwID))
  return 1
end

function OnMagicIconTooltip(dwID, dwCmdID, dwParam, pParam)
  window.settooltiptext(dwID, game.getmagicname(window.getappdata(dwID)))
  return 1
end

CHAR_MAGICSTATE_TIME = 0

function OnUpdateCharMagicState(dwID, dwCmdID, dwParam, pParam)
  local diff
  diff = window.getclockdur(CHAR_MAGICSTATE_TIME, window.getclock())
  if 1000 < diff then
    game.updatemagicstate()
    CHAR_MAGICSTATE_TIME = window.getclock()
  end
  return 1
end
