WND_DAILYEVENT = 0
WND_DAILYEVENT_X = 0
WND_DAILYEVENT_Y = 0
WND_DAILYEVENT_HELP = 0
DAILYEVENT_STAT_WND = 0
DAILYEVENT_STAT_ISLOCK = 0

function CreateDailyWnd()
  if window.isexist(WND_DAILYEVENT) then
    window.destroy(WND_DAILYEVENT)
    WND_DAILYEVENT = 0
    return
  end
  WND_DAILYEVENT = window.create(28181, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_DAILYEVENT_X or 0 > WND_DAILYEVENT_Y then
    window.move(WND_DAILYEVENT, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_DAILYEVENT, WND_DAILYEVENT_X, WND_DAILYEVENT_Y)
  end
  window.regsetting(WND_DAILYEVENT, "WND_DAILYEVENT")
  return 1
end

function OnOpenDailyWnd()
  CreateDailyWnd()
  game.getdailyeventdata()
end

function DestroyDailyWnd()
  WND_DAILYEVENT = 0
  return 1
end

function CreateDailyHelpWnd()
  if window.isexist(WND_DAILYEVENT_HELP) then
    window.destroy(WND_DAILYEVENT_HELP)
    WND_DAILYEVENT_HELP = 0
    return
  end
  WND_DAILYEVENT_HELP = window.create(28311, 0, 0, SYSTEM_HANDLER)
  window.move(WND_DAILYEVENT_HELP, SYSTEM_SCREEN_WIDTH / 2 - 200, SYSTEM_SCREEN_HEIGHT / 2)
  window.regsetting(WND_DAILYEVENT_HELP, "WND_DAILYEVENT_HELP")
  return 1
end

function OnGotoEventMap(dwID, dwCmdID, dwParam, pParam)
  game.gotodailyeventmap(dwCmdID)
  return 1
end

function OnEventHelp(dwID, dwCmdID, dwParam, pParam)
  game.showdailyeventhelp(dwCmdID)
  return 1
end

function CreateDailyStatWnd()
  if window.isexist(DAILYEVENT_STAT_WND) then
    window.destroy(DAILYEVENT_STAT_WND)
    DAILYEVENT_STAT_WND = 0
    return
  end
  DAILYEVENT_STAT_WND = window.create(28315, 0, 0, SYSTEM_HANDLER)
  window.move(DAILYEVENT_STAT_WND, SYSTEM_SCREEN_WIDTH - 180, SYSTEM_SCREEN_HEIGHT / 2)
  window.regsetting(DAILYEVENT_STAT_WND, "DAILYEVENT_STAT_WND")
  window.setbgcolor(DAILYEVENT_STAT_WND, 50, 50, 50, 50)
  return 1
end

function LockDailyEventStat(bLock)
  if bLock then
    window.modifystyle(DAILYEVENT_STAT_WND, wsTransparent, wsMoveable)
    window.modifystyle(window.find(DAILYEVENT_STAT_WND, 28317), wsTransparent, wsMoveable)
  else
    window.modifystyle(DAILYEVENT_STAT_WND, wsMoveable, wsTransparent)
    window.modifystyle(window.find(DAILYEVENT_STAT_WND, 28317), wsMoveable, wsTransparent)
  end
end

function OnDailyEventStat(dwID, dwCmdID, dwParam, pParam)
  DAILYEVENT_STAT_ISLOCK = window.ischeck(dwID)
  LockDailyEventStat(DAILYEVENT_STAT_ISLOCK)
  return 1
end
