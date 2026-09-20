WND_TUTIONWINDOW = 0
WND_TUTIONWINDOW_X = -1
WND_TUTIONWINDOW_Y = -1
TUITION_TIP_NUM = 0
EVENTTYPE_FIRST_LUMBING = 1
EVENTTYPE_FIRST_MINING = 2
EVENTTYPE_FIRST_GRATHERING = 3
EVENTTYPE_FIRST_FISHING = 4
EVENTTYPE_FIRST_ITEMTYPE_PET = 1
EVENTTYPE_FIRST_ITEMTYPE_HEAD = 2
EVENTTYPE_FIRST_ITEMTYPE_BODY = 3
lastScrollWndX = SYSTEM_SCREEN_WIDTH / 2
lastScrollWndY = SYSTEM_SCREEN_HEIGHT / 2
WND_TUTION_SCROLLWINDOW = 0

function CreateTuitionWnd()
  WND_TUTIONWINDOW = window.create(23030, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_TUTIONWINDOW_X or 0 > WND_TUTIONWINDOW_Y then
    window.move(WND_TUTIONWINDOW, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_TUTIONWINDOW, WND_TUTIONWINDOW_X, WND_TUTIONWINDOW_Y)
  end
  window.regsetting(WND_TUTIONWINDOW, "WND_TUTIONWINDOW")
end

function TuitionResetTips()
  game.gettuitiontipinfo()
  for i = 0, 7 do
    tipscrollw = window.find(WND_TUTIONWINDOW, 23031 + i)
    if i < TUITION_TIP_NUM and game.gettipshow() then
      window.show(tipscrollw, true)
    else
      window.show(tipscrollw, false)
    end
  end
end

function OnCloseTuitionWin(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_TUTION_SCROLLWINDOW) then
    lastScrollWndX = window.left(WND_TUTION_SCROLLWINDOW)
    lastScrollWndY = window.top(WND_TUTION_SCROLLWINDOW)
  end
  return 1
end

function OnTuitionTipButton(dwID, dwCmdID, dwParam, pParam)
  if WND_TUTION_SCROLLWINDOW > 0 and window.isexist(WND_TUTION_SCROLLWINDOW) then
    lastScrollWndX = window.left(WND_TUTION_SCROLLWINDOW)
    lastScrollWndY = window.top(WND_TUTION_SCROLLWINDOW)
    window.destroy(WND_TUTION_SCROLLWINDOW)
  end
  windowid = game.removetuitiontip(window.getappdata(dwID))
  if 0 < windowid then
    WND_TUTION_SCROLLWINDOW = window.create(windowid, 0, 0, SYSTEM_HANDLER)
    window.move(WND_TUTION_SCROLLWINDOW, lastScrollWndX, lastScrollWndY)
    tuicheckwnd = window.create(23049, WND_TUTION_SCROLLWINDOW, 0, SYSTEM_HANDLER)
    window.setcheck(tuicheckwnd, game.gettipshow())
  end
  return 1
end

function OnTuitionSetTipShow(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    game.settipshow(1)
  else
    game.settipshow(0)
  end
  TuitionResetTips()
  return 1
end

function TuitionEventFirstTalk(dwNpcID)
  return false
end

function TuitionEventFirstGather(nType)
  if nType == EVENTTYPE_FIRST_LUMBING then
    game.addtuitiontip(23290, 1386)
    return true
  end
  if nType == EVENTTYPE_FIRST_MINING then
    game.addtuitiontip(23300, 1386)
    return true
  end
  if nType == EVENTTYPE_FIRST_GRATHERING then
    game.addtuitiontip(23320, 1386)
    return true
  end
  if nType == EVENTTYPE_FIRST_FISHING then
    game.addtuitiontip(23310, 1386)
    return true
  end
  return false
end

function TuitionEventFirstDead()
  game.addtuitiontip(23150, 1386)
  return true
end

function TuitionEventFirstLoginMap(dwMapID)
  if dwMapID == 51 then
    game.addtuitiontip(23050, 1386)
    game.addtuitiontip(23060, 1386)
    return true
  end
  return false
end

function TuitionEventFirstLowEQDur()
  game.addtuitiontip(23260, 1386)
  return true
end

function TuitionEventFirstChooseClass()
  game.addtuitiontip(23080, 1386)
  return true
end

function TuitionEventFirstEndTalkMessage(dwMsgID)
  if dwMsgID == 5249 and WND_COMMAND ~= 0 and window.find(WND_COMMAND, 23500) == 0 then
    window.create(23500, WND_COMMAND, 0, SYSTEM_HANDLER)
    game.doshinewindow(4)
  end
  return false
end

function TuitionEventFirstGetTalkMessage(dwMsgID)
  if dwMsgID == 10013 then
    game.addtuitiontip(23140, 1386)
    return true
  end
  if dwMsgID == 10322 then
    game.addtuitiontip(23230, 1386)
    return true
  end
  if dwMsgID == 10419 then
    game.addtuitiontip(23240, 1386)
    return true
  end
  if dwMsgID == 5243 and WND_CHAR_INFO ~= 0 and window.find(WND_CHAR_INFO, 23500) == 0 then
    window.create(23500, WND_CHAR_INFO, 0, SYSTEM_HANDLER)
    game.doshinewindow(0)
  end
  if dwMsgID == 5245 and WND_QUICK_COMMAND ~= 0 and window.find(WND_QUICK_COMMAND, 23500) == 0 then
    window.create(23500, WND_QUICK_COMMAND, 0, SYSTEM_HANDLER)
    game.doshinewindow(1)
  end
  if dwMsgID == 5247 and WND_MINIMAP ~= 0 and window.find(WND_MINIMAP, 23500) == 0 then
    window.create(23500, WND_MINIMAP, 0, SYSTEM_HANDLER)
    game.doshinewindow(2)
  end
  if dwMsgID == 5251 and WND_CHAT ~= 0 and window.find(WND_CHAT, 23500) == 0 then
    window.create(23500, WND_CHAT, 0, SYSTEM_HANDLER)
    game.doshinewindow(3)
  end
  return false
end

function TuitionEventFirstLV(nLv)
  if nLv == 2 then
    game.addtuitiontip(23110, 1386)
    game.addtuitiontip(23400, 1386)
    return true
  end
  if nLv == 4 then
    game.addtuitiontip(23410, 1386)
    return true
  end
  if nLv == 10 then
    game.addtuitiontip(23420, 1386)
    return true
  end
  return false
end

function TuitionEventFirstFight()
  game.addtuitiontip(23200, 1386)
  return true
end

function TuitionEventFirstLowHp()
  game.addtuitiontip(23220, 1386)
  return true
end

function TuitionEventFirstSkillUp()
  game.addtuitiontip(23270, 1386)
  return true
end

function TuitionEventFirstQuestGot(dwQuestID)
  if dwQuestID == 101 then
    game.addtuitiontip(23180, 1386)
    return true
  end
end

function TuitionEventFirstGotItemType(dwItemType)
  if dwItemType == EVENTTYPE_FIRST_ITEMTYPE_PET then
    game.addtuitiontip(23280, 1386)
    return true
  end
  return false
end

function TuitionEventFirstCreateWnd(dwResID)
  if dwResID == 2301 then
    game.addtuitiontip(23350, 1386)
    return true
  end
  if dwResID == 3001 then
    game.addtuitiontip(23360, 1386)
    return true
  end
  if dwResID == 12002 then
    game.addtuitiontip(23370, 1386)
    return true
  end
  if dwResID == 572 then
    game.addtuitiontip(23390, 1386)
    return true
  end
  if dwResID == 293 then
    game.addtuitiontip(23340, 1386)
    return true
  end
  if dwResID == 434 then
    game.addtuitiontip(23330, 1386)
    return true
  end
  if dwResID == 556 then
    game.addtuitiontip(23380, 1386)
    return true
  end
  return false
end
