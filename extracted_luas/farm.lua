WND_FARM = 0
FARM_PLAYERSTAT_WND = 0
FARMPLAYER_STAT_ISLOCK = 0
WND_FARM_HELP = 0
WND_FARM_HELP_X = 0
WND_FARM_HELP_Y = 0

function CreateFarmControl()
  if window.isexist(WND_FARM) then
    window.destroy(WND_FARM)
    WND_FARM = 0
  end
  WND_FARM = window.create(24738, 0, 0, SYSTEM_HANDLER)
  window.regsetting(WND_FARM, "WND_FARM")
end

function OnFarmWater(dwID, dwCmdID, dwParam, pParam)
  game.farmwater()
  return 1
end

function OnFarmFertilize(dwID, dwCmdID, dwParam, pParam)
  game.farmfertilize()
  return 1
end

function OnFarmHarvest(dwID, dwCmdID, dwParam, pParam)
  game.farmharvest()
  return 1
end

function CreateFarmPlayerStatWnd()
  if window.isexist(FARM_PLAYERSTAT_WND) then
    window.destroy(FARM_PLAYERSTAT_WND)
    FARM_PLAYERSTAT_WND = 0
    return
  end
  FARM_PLAYERSTAT_WND = window.create(24743, 0, 0, SYSTEM_HANDLER)
  window.move(FARM_PLAYERSTAT_WND, SYSTEM_SCREEN_WIDTH - 180, SYSTEM_SCREEN_HEIGHT / 2)
  window.regsetting(FARM_PLAYERSTAT_WND, "FARM_PLAYERSTAT_WND")
  window.setbgcolor(FARM_PLAYERSTAT_WND, 50, 50, 50, 50)
  return 1
end

function LockFarmPlayerStat(bLock)
  if bLock then
    window.modifystyle(FARM_PLAYERSTAT_WND, wsTransparent, wsMoveable)
    window.modifystyle(window.find(FARM_PLAYERSTAT_WND, 24745), wsTransparent, wsMoveable)
  else
    window.modifystyle(FARM_PLAYERSTAT_WND, wsMoveable, wsTransparent)
    window.modifystyle(window.find(FARM_PLAYERSTAT_WND, 24745), wsMoveable, wsTransparent)
  end
end

function OnFarmPlayerStat(dwID, dwCmdID, dwParam, pParam)
  FARMPLAYER_STAT_ISLOCK = window.ischeck(dwID)
  LockFarmPlayerStat(FARMPLAYER_STAT_ISLOCK)
  return 1
end

function CreateFarmHelpWnd()
  if window.isexist(WND_FARM_HELP) then
    window.destroy(WND_FARM_HELP)
    WND_FARM_HELP = 0
    return
  end
  WND_FARM_HELP = window.create(24746, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_FARM_HELP_X or 0 > WND_FARM_HELP_Y then
    window.move(WND_FARM_HELP, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_FARM_HELP, WND_FARM_HELP_X, WND_FARM_HELP_Y)
  end
  window.regsetting(WND_FARM_HELP, "WND_FARM_HELP")
  return 1
end
