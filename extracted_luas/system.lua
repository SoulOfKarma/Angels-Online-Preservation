function OnAcceptMinigame(dwID, dwCmdID, dwParam, pParam)
  game.joinminigame(true)
  
  window.destroy(window.parent(dwID))
  return 1
end

function OnDenyMinigame(dwID, dwCmdID, dwParam, pParam)
  game.joinminigame(false)
  window.destroy(window.parent(dwID))
  return 1
end

WND_NPCINFO = 0
WND_NPCINFO_X = -1
WND_NPCINFO_Y = -1
WND_AUTOROBOT = 0
WND_AUTOROBOT_X = -1
WND_AUTOROBOT_Y = -1
WND_AUTOFIGHT = 0
WND_AUTOASSIST = 0
WND_AUTOPET = 0
WND_AUTOPRODUCE = 0
WND_AUTOOTHER = 0
WND_AUTOHISTORYLOG = 0
WND_AUTOSUPPLY = 0
WND_AUTOMALL = 0
AUTOROBOT_WINDOW_RES_ID = 14200
FIGHT_WINDOW_RES_ID = 959
ASSIST_WINDOW_RES_ID = 14000
PET_WINDOW_RES_ID = 24600
PRODUCE_WINDOW_RES_ID = 14310
OTHER_WINDOW_RES_ID = 2401
SUPPLY_WINDOW_RES_ID = 10054
HISTORYLOG_WINDOW_RES_ID = 14300
AUTOMALL_WINDOW_RES_ID = 10096
G_BOOL_INITIAL = false
AUTOSUPPLY_ENABLE = 0
AUTOROBOT_CHECK_RES_ID = 14219
AUTOROBOT_RADIO_RES_ID_FIRST = 14210
DATAID_USED_TP_ITEM = 2000
DATAID_AUTOROBOT_ISOPEN_CHECK = 2200
DATAID_AUTOROBOT_PAGE_RADIO = 2201

function OnClickWizard(dwID, dwCmdID, dwParam, pParam)
  if game.isdef("__WATERMELON") then
    if game.watermelonlockrobot() == 1 then
      game.addsystemmessage(2686)
    else
      CreateRobotWindow()
    end
  else
    CreateRobotWindow()
  end
  return 1
end

function CreateRobotWindow()
  if window.isexist(WND_AUTOROBOT) then
    if window.isvisible(WND_AUTOROBOT) then
      window.show(WND_AUTOROBOT, false)
    else
      window.show(WND_AUTOROBOT, true)
      window.setforeground(WND_AUTOROBOT)
    end
    return
  end
  if AUTOSUPPLY_ENABLE == 1 then
    if game.dosafeverify(12) ~= 1 then
      return 1
    end
    OnCreateRobotWindow()
  else
    OnCreateRobotWindow()
  end
  return 1
end

function OnCreateRobotWindow()
  WND_AUTOROBOT = window.create(AUTOROBOT_WINDOW_RES_ID, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_AUTOROBOT_X or 0 > WND_AUTOROBOT_Y then
    window.move(WND_AUTOROBOT, 100, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_AUTOROBOT, WND_AUTOROBOT_X, WND_AUTOROBOT_Y)
  end
  WND_AUTOFIGHT = window.find(WND_AUTOROBOT, FIGHT_WINDOW_RES_ID)
  WND_AUTOASSIST = window.find(WND_AUTOROBOT, ASSIST_WINDOW_RES_ID)
  WND_AUTOPET = window.find(WND_AUTOROBOT, PET_WINDOW_RES_ID)
  WND_AUTOPRODUCE = window.find(WND_AUTOROBOT, PRODUCE_WINDOW_RES_ID)
  WND_AUTOOTHER = window.find(WND_AUTOROBOT, OTHER_WINDOW_RES_ID)
  if game.isdef("__ROBOT_MALL") then
    WND_AUTOMALL = window.find(WND_AUTOROBOT, AUTOMALL_WINDOW_RES_ID)
    window.show(WND_AUTOMALL, true)
  else
    window.show(window.find(WND_AUTOROBOT, AUTOMALL_WINDOW_RES_ID), false)
    window.show(window.find(WND_AUTOROBOT, 14216), false)
  end
  WND_AUTOHISTORYLOG = window.find(WND_AUTOROBOT, HISTORYLOG_WINDOW_RES_ID)
  if game.isdef("__ROBOT2") then
    WND_AUTOSUPPLY = window.find(WND_AUTOROBOT, SUPPLY_WINDOW_RES_ID)
    window.show(WND_AUTOSUPPLY, true)
  else
    window.show(window.find(WND_AUTOROBOT, SUPPLY_WINDOW_RES_ID), false)
    window.show(window.find(WND_AUTOROBOT, 14214), false)
  end
  window.regsetting(WND_AUTOROBOT, "WND_AUTOROBOT")
  if G_BOOL_INITIAL == false then
    G_BOOL_INITIAL = true
  end
  local nCheckWndHD = window.find(WND_AUTOROBOT, AUTOROBOT_CHECK_RES_ID)
  window.setcheck(nCheckWndHD, game.getrobotvar_bool(DATAID_AUTOROBOT_ISOPEN_CHECK))
  local nSelectedPageWndHD = window.find(WND_AUTOROBOT, AUTOROBOT_RADIO_RES_ID_FIRST + game.getrobotvar_int(DATAID_AUTOROBOT_PAGE_RADIO))
  window.setcheck(nSelectedPageWndHD, true)
  OnRadioRobotChange(nSelectedPageWndHD, 0, 0, 0)
  CreateAutoFightWnd(WND_AUTOFIGHT)
  CreateAssistWindow(WND_AUTOASSIST)
  CreateAutoPetWindow(WND_AUTOPET)
  CreateAutoProduceWindow(WND_AUTOPRODUCE)
  CreateAutoOtherWnd(WND_AUTOOTHER)
  CreateHistoryLogWindow(WND_AUTOHISTORYLOG)
  if game.isdef("__ROBOT_MALL") then
    CreateAutoMallWnd(WND_AUTOMALL)
  end
  if game.isdef("__ROBOT2") then
    CreateAutoSupplyWnd(WND_AUTOSUPPLY)
  end
  return 1
end

function OnRadioRobotChange(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local nSelectedIndex = appdata - AUTOROBOT_RADIO_RES_ID_FIRST + 1
  local pWndResID = {
    FIGHT_WINDOW_RES_ID,
    ASSIST_WINDOW_RES_ID,
    PET_WINDOW_RES_ID,
    PRODUCE_WINDOW_RES_ID,
    SUPPLY_WINDOW_RES_ID,
    OTHER_WINDOW_RES_ID,
    AUTOMALL_WINDOW_RES_ID,
    0,
    HISTORYLOG_WINDOW_RES_ID
  }
  for i = 1, 9 do
    if pWndResID[i] ~= 0 then
      if i == nSelectedIndex then
        window.show(window.find(window.parent(dwID), pWndResID[i]), true)
        game.setrobotvar_int(DATAID_AUTOROBOT_PAGE_RADIO, i - 1)
      else
        window.show(window.find(window.parent(dwID), pWndResID[i]), false)
      end
    end
  end
  return 1
end

function OnOpenOrCloseRobot(bIsRun)
  game.setrobotvar_bool(DATAID_USED_TP_ITEM, false)
  game.setrobotisrun(bIsRun)
  game.setrobotvar_bool(DATAID_AUTOROBOT_ISOPEN_CHECK, bIsRun)
  if bIsRun then
    game.insertstringtohistory(game.getstring(1961))
    game.addsystemmessage(1961)
    if game.isdef("__ROBOT2_PLUS") then
      game.setrobotvar_bool(AS_BOL_CONTINUEEXERCISE, true)
    end
  else
    game.insertstringtohistory(game.getstring(1962))
    game.addsystemmessage(1962)
  end
  return 1
end

function OnClickOpenCloseRobot(dwID, dwCmdID, dwParam, pParam)
  local bIsRun = window.ischeck(dwID)
  OnOpenOrCloseRobot(bIsRun)
  return 1
end

function OnClickCloseRobotWnd(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  window.show(dwMainWndHD, false)
  return 1
end
