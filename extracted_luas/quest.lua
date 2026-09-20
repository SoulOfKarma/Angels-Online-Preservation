WND_QUEST = 0
WND_DELETE_QUEST = 0
WND_QUEST_X = -1
WND_QUEST_Y = -1
WND_QUEST_SHORTCUT = 0
WND_QUEST_SHORTCUT_X = -1
WND_QUEST_SHORTCUT_Y = -1
QUEST_SHORTCUT_ISLOCK = false

function CreateQuestWnd()
  local w
  if window.isexist(WND_QUEST) then
    if window.isvisible(WND_QUEST) then
      window.show(WND_QUEST, false)
    else
      window.show(WND_QUEST, true)
      window.setforeground(WND_QUEST)
    end
    return
  end
  WND_QUEST = window.create(434, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_QUEST_X or 0 > WND_QUEST_Y then
    window.move(WND_QUEST, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_QUEST, WND_QUEST_X, WND_QUEST_Y)
  end
  window.regsetting(WND_QUEST, "WND_QUEST")
  if not game.isdef("__JAPAN") and not game.isdef("__INDONESIA") then
    w = window.find(WND_QUEST, 440)
    window.show(w, false)
  end
  w = window.find(WND_QUEST, 438)
  window.setradio(w, 0)
  game.initquestlist()
  game.inittreasuremap()
  if game.isdef("__SPECTREASUREMAPEX") then
    w = window.find(WND_QUEST, 12373)
    window.show(w, true)
    w = window.find(WND_QUEST, 12395)
    window.show(w, true)
    game.initspectreasuremapex()
  end
  return 1
end

function OnQuestClose()
  if window.isexist(WND_QUEST) then
    window.show(WND_QUEST, false)
    return 0
  end
end

function OnQuestCheck(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  if appdata == 438 then
    window.show(window.find(window.parent(dwID), 441), true)
    window.show(window.find(window.parent(dwID), 442), false)
    window.show(window.find(window.parent(dwID), 12330), false)
    window.show(window.find(window.parent(dwID), 12352), false)
    window.show(window.find(window.parent(dwID), 12374), false)
  elseif appdata == 439 then
    window.show(window.find(window.parent(dwID), 441), false)
    window.show(window.find(window.parent(dwID), 442), true)
    window.show(window.find(window.parent(dwID), 12330), false)
    window.show(window.find(window.parent(dwID), 12352), false)
    window.show(window.find(window.parent(dwID), 12374), false)
  elseif appdata == 440 then
    window.show(window.find(window.parent(dwID), 441), false)
    window.show(window.find(window.parent(dwID), 442), false)
    window.show(window.find(window.parent(dwID), 12330), true)
    window.show(window.find(window.parent(dwID), 12352), false)
    window.show(window.find(window.parent(dwID), 12374), false)
  elseif appdata == 12373 then
    window.show(window.find(window.parent(dwID), 441), false)
    window.show(window.find(window.parent(dwID), 442), false)
    window.show(window.find(window.parent(dwID), 12330), false)
    window.show(window.find(window.parent(dwID), 12352), true)
    window.show(window.find(window.parent(dwID), 12374), false)
  elseif appdata == 12395 then
    window.show(window.find(window.parent(dwID), 441), false)
    window.show(window.find(window.parent(dwID), 442), false)
    window.show(window.find(window.parent(dwID), 12330), false)
    window.show(window.find(window.parent(dwID), 12352), false)
    window.show(window.find(window.parent(dwID), 12374), true)
  end
  return 1
end

function OnDeleteQuest(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_DELETE_QUEST) then
    return 1
  end
  WND_DELETE_QUEST = window.create(456, window.parent(dwID), 0, 0)
  window.move(WND_DELETE_QUEST, window.left(WND_QUEST) + window.width(WND_QUEST) / 2, window.top(WND_QUEST) + window.height(WND_QUEST) / 2)
  return 1
end

function OnDeleteQuest_OK(dwID, dwCmdID, dwParam, pParam)
  game.deletequest(window.parent(window.parent(dwID)))
  window.destroy(window.parent(dwID))
  return 1
end

function OnDeleteQuest_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnFindQuestNpc(dwID, dwCmdID, dwParam, pParam)
  game.findnpc(1)
  CreateStageMapWnd()
  return 1
end

function IsInRange(mx, my, x1, y1, x2, y2)
  if x1 <= mx and mx <= x2 and y1 <= my and my <= y2 then
    return true
  else
    return false
  end
end

function ClickQuestShortcut()
  if game.isquestshortcutenable() then
    game.enablequestshortcut(false)
  elseif game.enablequestshortcut(true) and window.isexist(WND_QUEST_SHORTCUT) == false then
    ShowHideQuestShortcut(true)
  end
end

function OnSelectQuest(dwID, dwCmdID, dwParam, pParam)
  local mx, my, nRow, w, x1, y1, x2, y2
  if window.ischilditem(dwID, dwParam) == true then
    window.enable(window.find(window.parent(dwID), 444), true)
  else
    window.enable(window.find(window.parent(dwID), 444), false)
  end
  w = window.find(WND_QUEST, 445)
  mx, my = window.getsysmousexy()
  x1, y1, x2, y2 = window.getitemrange(w, window.getcheckitem(w))
  if IsInRange(mx, my, x1, y1, x1 + 24, y2) then
    ClickQuestShortcut()
  end
  game.updatequestcontent()
  return 1
end

function OnCheckQuestShortcut(dwID, dwCmdID, dwParam, pParam)
  game.enablequestshortcut(window.ischeck(dwID))
  if window.ischeck(dwID) and window.isexist(WND_QUEST_SHORTCUT) == false then
    ShowHideQuestShortcut(true)
  else
    game.updatequestshortcut()
  end
  return 1
end

function OnClickQuestShortcut(dwID, dwCmdID, dwParam, pParam)
  ShowHideQuestShortcut(window.ischeck(dwID))
  return 1
end

function ShowHideQuestShortcut(bShow)
  if bShow then
    if window.isexist(WND_QUEST_SHORTCUT) == false then
      WND_QUEST_SHORTCUT = window.create(671, 0, 0, SYSTEM_HANDLER)
      window.regsetting(WND_QUEST_SHORTCUT, "WND_QUEST_SHORTCUT")
      game.updatequestshortcut()
      window.setbgcolor(WND_QUEST_SHORTCUT, 50, 50, 50, 50)
      if 0 > WND_QUEST_SHORTCUT_X or WND_QUEST_SHORTCUT_X >= SYSTEM_SCREEN_WIDTH or 0 > WND_QUEST_SHORTCUT_Y or WND_QUEST_SHORTCUT_Y >= SYSTEM_SCREEN_HEIGHT then
        window.move(WND_QUEST_SHORTCUT, SYSTEM_SCREEN_WIDTH - window.width(WND_QUEST_SHORTCUT), window.top(WND_QUEST_SHORTCUT))
      else
        window.move(WND_QUEST_SHORTCUT, WND_QUEST_SHORTCUT_X, WND_QUEST_SHORTCUT_Y)
      end
      window.setcheck(window.find(WND_QUEST_SHORTCUT, 672), QUEST_SHORTCUT_ISLOCK)
      LockQuestShortcut(QUEST_SHORTCUT_ISLOCK)
      window.setcheck(window.find(WND_QUEST, 670), true)
      return true
    end
  elseif window.isexist(WND_QUEST_SHORTCUT) then
    window.destroy(WND_QUEST_SHORTCUT)
    window.setcheck(window.find(WND_QUEST, 670), false)
    return true
  end
  return false
end

function LockQuestShortcut(bLock)
  if bLock then
    window.modifystyle(WND_QUEST_SHORTCUT, wsTransparent, wsMoveable)
    window.modifystyle(window.find(WND_QUEST_SHORTCUT, 673), wsTransparent, wsMoveable)
  else
    window.modifystyle(WND_QUEST_SHORTCUT, wsMoveable, wsTransparent)
    window.modifystyle(window.find(WND_QUEST_SHORTCUT, 673), wsMoveable, wsTransparent)
  end
end

function OnLockQuestShortcut(dwID, dwCmdID, dwParam, pParam)
  QUEST_SHORTCUT_ISLOCK = window.ischeck(dwID)
  LockQuestShortcut(QUEST_SHORTCUT_ISLOCK)
  return 1
end

function OnDeleteTreasureMapWnd(dwID, dwCmdID, dwParam, pParam)
  local wnd = window.create(12316, window.parent(dwID), 0, 0)
  return 1
end

function DeleteTreasureMap(dwID, dwCmdID, dwParam, pParam)
  game.deletetreasuremap(0)
  window.destroy(window.parent(dwID))
  return 1
end

function OnDeleteSpecTreasureMapWnd(dwID, dwCmdID, dwParam, pParam)
  local wnd = window.create(12346, window.parent(dwID), 0, 0)
  return 1
end

function DeleteSpecTreasureMap(dwID, dwCmdID, dwParam, pParam)
  game.deletetreasuremap(1)
  window.destroy(window.parent(dwID))
  return 1
end

function OnDeleteSpecTreasureMapWndEx(dwID, dwCmdID, dwParam, pParam)
  if window.getappdata(dwID) == 2 then
    window.create(12369, window.parent(dwID), 0, 0)
  else
    window.create(12391, window.parent(dwID), 0, 0)
  end
  return 1
end

function DeleteSpecTreasureMapEx(dwID, dwCmdID, dwParam, pParam)
  game.deletetreasuremap(window.getappdata(dwID))
  window.destroy(window.parent(dwID))
  return 1
end
