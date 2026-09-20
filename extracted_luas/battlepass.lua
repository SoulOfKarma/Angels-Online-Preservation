WND_BATTLE_PASS = 0
WND_BATTLE_PASS_X = -1
WND_BATTLE_PASS_Y = -1
WND_BATTLE_PASS_PAGE = 1
WND_BATTLE_PASS_CONFIRM = 0
WND_BATTLE_PASS_ACTION = 0

function CreateBattlePassWnd()
  if window.isexist(WND_BATTLE_PASS) then
    window.destroy(WND_BATTLE_PASS)
    WND_BATTLE_PASS = 0
  else
    WND_BATTLE_PASS_X = WND_ACTBOARD_X
    WND_BATTLE_PASS_Y = WND_ACTBOARD_Y
    WND_BATTLE_PASS = window.create(16501, 0, 0, SYSTEM_HANDLER)
    window.move(WND_BATTLE_PASS, WND_BATTLE_PASS_X, WND_BATTLE_PASS_Y)
    window.regsetting(WND_BATTLE_PASS, "WND_BATTLE_PASS")
    game.BattlePassOpen(WND_BATTLE_PASS_PAGE)
  end
  return 1
end

function OnBattlePassaAction(dwID, dwCmdID, dwParam, pParam)
  local action
  action = window.getappdata(dwID)
  if action == 1 then
    game.BattlePassAction(4)
  elseif action == 2 then
    game.BattlePassAction(2)
  elseif action == 3 then
    game.BattlePassAction(3)
  end
  return 1
end

function OnBattlePassChangePage(dwID, dwCmdID, dwParam, pParam)
  local page
  page = window.getappdata(dwID)
  game.BattlePassChangePage(page)
  return 1
end

function CreateBattlePassConfirm(action)
  if WND_BATTLE_PASS <= 0 then
    return 0
  end
  local strID = 0
  if action == 2 then
    strID = 4132
  elseif action == 4 then
    strID = 4134
  else
    return 0
  end
  if window.isexist(WND_BATTLE_PASS_CONFIRM) then
    window.destroy(WND_BATTLE_PASS_CONFIRM)
  end
  WND_BATTLE_PASS_CONFIRM = window.create(16537, WND_BATTLE_PASS, 0, 0)
  window.settitle(window.find(WND_BATTLE_PASS_CONFIRM, 16538), game.getstring(strID))
  WND_BATTLE_PASS_ACTION = action
  return 1
end

function OnBattlePassaActionOK(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(74, WND_BATTLE_PASS_ACTION)
  CloseBattlePassConfirm()
  return 1
end

function OnBattlePassaActionCancel(dwID, dwCmdID, dwParam, pParam)
  CloseBattlePassConfirm()
  return 1
end

function CloseBattlePassConfirm()
  WND_BATTLE_PASS_ACTION = 0
  if window.isexist(WND_BATTLE_PASS_CONFIRM) then
    window.destroy(WND_BATTLE_PASS_CONFIRM)
    WND_BATTLE_PASS_CONFIRM = 0
  end
  return 1
end

function OnCloseBattlePassWnd(dwID, dwCmdID, dwParam, pParam)
  CloseBattlePassWnd()
  return 1
end

function CloseBattlePassWnd()
  if window.isexist(WND_BATTLE_PASS) then
    window.destroy(WND_BATTLE_PASS)
    WND_BATTLE_PASS = 0
    WND_ACTBOARD_X = WND_BATTLE_PASS_X
    WND_ACTBOARD_Y = WND_BATTLE_PASS_Y
  end
  return 1
end
