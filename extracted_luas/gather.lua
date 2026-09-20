WND_GATHERING = 0
WND_GATHERING_X = -1
WND_GATHERING_Y = -1
GATHER_TIME = 0
GATHER_START_CLOCK = 0
GATHER_ANIMATE = true

function ShowGatherWnd(pMatName, nGatherTime)
  local w
  if window.isexist(WND_GATHERING) == false then
    WND_GATHERING = window.create(387, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_GATHERING_X or 0 > WND_GATHERING_Y then
      window.move(WND_GATHERING, (SYSTEM_SCREEN_WIDTH - window.width(WND_GATHERING)) / 2, 60)
    else
      window.move(WND_GATHERING, WND_GATHERING_X, WND_GATHERING_Y)
    end
    window.regsetting(WND_GATHERING, "WND_GATHERING")
  end
  w = window.find(WND_GATHERING, 388)
  window.setrange(w, 0, 100)
  window.setpos(w, 0)
  if 500 < nGatherTime then
    nGatherTime = nGatherTime - 500
  end
  GATHER_TIME = nGatherTime
  GATHER_START_CLOCK = window.getclock()
  GATHER_ANIMATE = true
  window.show(WND_GATHERING, true)
end

function HideGatherWnd()
  if window.isexist(WND_GATHERING) then
    window.destroy(WND_GATHERING)
    GATHER_ANIMATE = false
  end
end

function OnUpdateGather(dwID, dwCmdID, dwParam, pParam)
  local x, y, w, t, pos
  if GATHER_ANIMATE == true then
    t = window.getclock() - GATHER_START_CLOCK
    if t >= GATHER_TIME then
      pos = 100
      GATHER_ANIMATE = false
    else
      pos = t * 100 / GATHER_TIME
    end
    w = window.find(WND_GATHERING, 388)
    window.setpos(w, pos)
  end
  return 1
end
