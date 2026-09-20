WND_SALON = 0
WND_SALON_TYPE = 0

function CreateSalonWnd(nID, nType)
  local Wnd_hd, x, y
  if window.isexist(WND_SALON) then
    window.destroy(WND_SALON)
    WND_SALON = 0
    WND_SALON_TYPE = 0
  end
  WND_SALON = window.create(nID, 0, 0, SYSTEM_HANDLER)
  WND_SALON_TYPE = nType
  x = SYSTEM_SCREEN_WIDTH / 2 - window.width(WND_SALON) / 2
  y = SYSTEM_SCREEN_HEIGHT / 2 - window.height(WND_SALON) / 2
  window.move(WND_SALON, x, y)
  game.initsalonwnd(WND_SALON, WND_SALON_TYPE)
  return 1
end

function TurnSalonWnd01()
  game.turnsalonfitting(-32)
  return 1
end

function TurnSalonWnd02()
  game.turnsalonfitting(32)
  return 1
end

function SalonFitting()
  game.salonfitting()
  return 1
end

function SalonTallFittingUP()
  game.salontallfitting(1)
  return 1
end

function SalonTallFittingDown()
  game.salontallfitting(-1)
  return 1
end

function SalonCheckOK()
  local Wnd, Wnd2, x, y
  if WND_SALON_TYPE >= 1 and WND_SALON_TYPE <= 4 then
    Wnd = window.create(12950, WND_SALON, 0, SYSTEM_HANDLER)
    x = SYSTEM_SCREEN_WIDTH / 2 - window.width(Wnd) / 2
    y = SYSTEM_SCREEN_HEIGHT / 2 - window.height(Wnd) / 2
    window.move(Wnd, x, y)
    Wnd2 = window.find(Wnd, 12951)
    window.settitle(Wnd2, game.getstring(2127))
  end
  return 1
end

function SalonOK()
  game.salonok(WND_SALON, WND_SALON_TYPE)
  window.destroy(WND_SALON)
  WND_SALON = 0
  WND_SALON_TYPE = 0
  return 1
end
