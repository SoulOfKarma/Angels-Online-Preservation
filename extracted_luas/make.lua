WND_MAKE = 0
WND_MAKE_X = -1
WND_MAKE_Y = -1

function OnMakeClose(dwID, dwCmdID, dwParam, pParam)
  game.makestop(WND_MAKE)
  window.destroy(WND_MAKE)
  WND_MAKE = 0
  return 1
end

function OnMakeClassWnd(dwID, dwCmdID, dwParam, pParam)
  game.initmakeclasswnd(WND_MAKE)
  return 1
end

function OnMakeSelectClass(dwID, dwCmdID, dwParam, pParam)
  game.makeselectclass(dwID, dwParam)
  return 1
end

function OnMakeEditChange(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, -1)
  game.makeitemnum(window.parent(dwID))
  return 1
end

function OnMakeScroll(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, dwParam)
  game.makeitemnum(window.parent(dwID))
  return 1
end

function OnMakeAdd(dwID, dwCmdID, dwParam, pParam)
  game.makeadd(window.parent(dwID))
  return 1
end

function OnMakeDel(dwID, dwCmdID, dwParam, pParam)
  game.makedel(window.parent(dwID))
  return 1
end

function OnMakeStart(dwID, dwCmdID, dwParam, pParam)
  game.makestart(window.parent(dwID))
  return 1
end

function OnMakeSelectItem(dwID, dwCmdID, dwParam, pParam)
  game.makeselectitem(dwID, dwParam)
  return 1
end

function OnMakeStopMessage(dwID, dwCmdID, dwParam, pParam)
  local dwWnd = window.create(2836, WND_MAKE, 0, 0)
  window.moveoffset(dwWnd, window.width(WND_MAKE) / 2 - 83, window.height(WND_MAKE) / 2 - 50)
  return 1
end

function OnMakeStop_OK(dwID, dwCmdID, dwParam, pParam)
  game.makestop(WND_MAKE)
  window.destroy(window.parent(dwID))
  return 1
end

function OnMakeStop_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnMakeMax(dwID, dwCmdID, dwParam, pParam)
  game.makemax(window.parent(dwID))
  return 1
end

WND_MAKING = 0
WND_MAKING_X = -1
WND_MAKING_Y = -1
MAKE_TIME = 0
MAKE_START_CLOCK = 0
MAKE_ANIMATE = true

function ShowMakeWnd(nMakeTime)
  local w
  HideMakeWnd()
  if window.isexist(WND_MAKING) == false then
    WND_MAKING = window.create(2872, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_MAKING_X or 0 > WND_MAKING_Y then
      window.move(WND_MAKING, (SYSTEM_SCREEN_WIDTH - window.width(WND_MAKING)) / 2, 60)
    else
      window.move(WND_MAKING, WND_MAKING_X, WND_MAKING_Y)
    end
    window.regsetting(WND_MAKING, "WND_MAKING")
  end
  w = window.find(WND_MAKING, 2873)
  window.setrange(w, 0, 100)
  window.setpos(w, 0)
  MAKE_TIME = nMakeTime * 1000 - 500
  MAKE_START_CLOCK = window.getclock()
  MAKE_ANIMATE = true
end

function HideMakeWnd()
  if window.isexist(WND_MAKING) then
    window.destroy(WND_MAKING)
    MAKE_ANIMATE = false
  end
end

function OnUpdateMake(dwID, dwCmdID, dwParam, pParam)
  local x, y, w, t, pos
  if MAKE_ANIMATE == true then
    t = window.getclock() - MAKE_START_CLOCK
    if t >= MAKE_TIME then
      pos = 100
      MAKE_ANIMATE = false
    else
      pos = t * 100 / MAKE_TIME
    end
    w = window.find(WND_MAKING, 2873)
    window.setpos(w, pos)
  end
  return 1
end

function OnMakeClassSkillWnd(dwID, dwCmdID, dwParam, pParam)
  game.initmakeclassskillwnd(window.parent(dwID))
  return 1
end

function OnMakeSkillSelectClass(dwID, dwCmdID, dwParam, pParam)
  game.makeskillselectclass(window.parent(dwID), dwParam)
  return 1
end
