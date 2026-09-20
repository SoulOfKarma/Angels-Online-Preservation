WND_ACTBOARD = 0
WND_ACTBOARD_OPEN_SORT = 1
WND_ACTBOARD_X = -1
WND_ACTBOARD_Y = -1

function CreateActBoardWnd()
  CloseBattlePassWnd()
  if window.isexist(WND_ACTBOARD) then
    window.destroy(WND_ACTBOARD)
    WND_ACTBOARD = 0
  else
    WND_ACTBOARD = window.create(16200, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_ACTBOARD_X or 0 > WND_ACTBOARD_Y then
      window.move(WND_ACTBOARD, (SYSTEM_SCREEN_WIDTH - window.width(WND_ACTBOARD)) / 2, (SYSTEM_SCREEN_HEIGHT - window.height(WND_ACTBOARD)) / 2)
    else
      window.move(WND_ACTBOARD, WND_ACTBOARD_X, WND_ACTBOARD_Y)
    end
    window.regsetting(WND_ACTBOARD, "WND_ACTBOARD")
    game.initActBoardListBtn()
    game.openActBoardTypeWnd()
  end
  return 1
end

function OnClickActBoardListBtn(dwID, dwCmdID, dwParam, pParam)
  game.onClickActBoardListBtn()
  return 1
end

function SetActBoardTitle(title)
  window.settitle(window.find(WND_ACTBOARD, 16204), title)
  return 1
end

function OnActBoardOpenExplainWnd(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function HideActBoardAllTypeWnd()
  window.show(window.find(WND_ACTBOARD, 16211), false)
  window.show(window.find(WND_ACTBOARD, 16231), false)
  window.show(window.find(WND_ACTBOARD, 16250), false)
  window.show(window.find(WND_ACTBOARD, 16260), false)
end

function ShowActBoardTypeWnd(type)
  local resID = 0
  if type == 1 then
    resID = 16211
  elseif type == 2 then
    resID = 16231
  elseif type == 3 then
    resID = 0
  elseif type == 4 then
    resID = 16250
  elseif type == 5 then
    resID = 0
  elseif type == 6 then
    resID = 16260
  elseif type == 7 then
    resID = 0
  elseif type == 8 then
    resID = 0
  end
  window.show(window.find(WND_ACTBOARD, resID), true)
  return 1
end

function OnClickABLoginRaward(dwID, dwCmdID, dwParam, pParam)
  local rewardid
  rewardid = window.getappdata(dwID)
  if 0 < rewardid then
    game.netcommand(54, rewardid)
  end
  return 1
end

function OnClickABOnlineRaward(dwID, dwCmdID, dwParam, pParam)
  local rewardid
  rewardid = window.getappdata(dwID)
  if 0 < rewardid then
    game.netcommand(72, rewardid)
  end
  return 1
end

function UpdateABLoginRawardData()
  game.updateABLoginRawardData()
  return 1
end

function UpdateABOnlineRawardData()
  game.updateABOnlineRawardData()
  return 1
end

function OnClickABActURL(dwID, dwCmdID, dwParam, pParam)
  local idx
  idx = window.getappdata(dwID)
  if 0 < idx then
    game.openABActURL(idx)
  end
  return 1
end

function OnClickABExchange(dwID, dwCmdID, dwParam, pParam)
  local groupID
  groupID = window.getappdata(dwID)
  if 0 < groupID then
    CloseActBoardWnd()
    game.netcommand(73, groupID)
  end
  return 1
end

function CloseActBoardWnd()
  if window.isexist(WND_ACTBOARD) then
    window.destroy(WND_ACTBOARD)
    WND_ACTBOARD = 0
  end
end
