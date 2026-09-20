WND_ROULETTE = 0
WND_ROULETTE_LOG = 0
WND_ROULETTE_LOG_X = 0
WND_ROULETTE_LOG_Y = 0
WND_ROULETTE_LOG_SHOW = 1

function CreateRouletteWnd()
  OnRouletteLogWndOpen()
  if window.isexist(WND_ROULETTE) then
    window.destroy(WND_ROULETTE)
    WND_ROULETTE = 0
  end
  WND_ROULETTE = window.create(16901, 0, 0, SYSTEM_HANDLER)
  window.move(WND_ROULETTE, (SYSTEM_SCREEN_WIDTH - window.width(WND_ROULETTE)) / 2, (SYSTEM_SCREEN_HEIGHT - window.height(WND_ROULETTE)) / 2)
  window.regsetting(WND_ROULETTE, "WND_ROULETTE")
  return 1
end

function OnRouletteClose(dwID, dwCmdID, dwParam, pParam)
  DoRouletteClose()
  return 1
end

function DoRouletteClose()
  OnRouletteAllClose()
  game.rouletteclose()
end

function OnRouletteAllClose()
  if window.isexist(WND_ROULETTE) then
    window.destroy(WND_ROULETTE)
    WND_ROULETTE = 0
  end
  if window.isexist(WND_ROULETTE_LOG) then
    window.destroy(WND_ROULETTE_LOG)
    WND_ROULETTE_LOG = 0
  end
  return 1
end

function OnRouletteOpenLogWnd(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_ROULETTE_LOG) then
    if window.isvisible(WND_ROULETTE_LOG) then
      window.show(WND_ROULETTE_LOG, false)
    else
      window.show(WND_ROULETTE_LOG, true)
      window.move(WND_ROULETTE_LOG, 0, (SYSTEM_SCREEN_HEIGHT - window.height(WND_ROULETTE_LOG)) / 2)
    end
  end
  return 1
end

function OnRouletteLogWndOpen()
  if window.isexist(WND_ROULETTE_LOG) then
    window.destroy(WND_ROULETTE_LOG)
    WND_ROULETTE_LOG = 0
  end
  WND_ROULETTE_LOG = window.create(16924, 0, 0, SYSTEM_HANDLER)
  window.move(WND_ROULETTE_LOG, 0, (SYSTEM_SCREEN_HEIGHT - window.height(WND_ROULETTE_LOG)) / 2)
  window.regsetting(WND_ROULETTE_LOG, "WND_ROULETTE_LOG")
  window.settitle(WND_ROULETTE_LOG, game.getstring(3789))
  window.settitle(window.find(WND_ROULETTE_LOG, 16925), game.getstring(3785))
  window.settitle(window.find(WND_ROULETTE_LOG, 16926), game.getstring(3786))
  window.settitle(window.find(WND_ROULETTE_LOG, 16927), game.getstring(3787))
  window.settitle(window.find(WND_ROULETTE_LOG, 16930), game.getstring(3799))
  window.show(WND_ROULETTE_LOG, true)
  return 1
end

function OnRouletteLogWndClose()
  if window.isexist(WND_ROULETTE_LOG) then
    window.show(WND_ROULETTE_LOG, false)
  end
  return 0
end

function SetRouletteTitle(title)
  window.settitle(window.find(WND_ROULETTE, 16907), title)
  return 1
end

function SetRouletteCountdown(time)
  window.settitle(window.find(WND_ROULETTE, 16908), time)
  return 1
end

function SetRouletteFreeInfo(info)
  window.settitle(window.find(WND_ROULETTE, 16909), info)
  return 1
end

function SetRouletteStartBtnType(type)
  window.show(window.find(WND_ROULETTE, 16922), false)
  window.show(window.find(WND_ROULETTE, 16905), false)
  window.show(window.find(WND_ROULETTE, 16906), false)
  local resID = 0
  if type == 0 then
    resID = 16922
  elseif type == 1 then
    resID = 16906
  elseif type == 2 then
    resID = 16905
  else
    return 0
  end
  window.show(window.find(WND_ROULETTE, resID), true)
  return 1
end

function SetRouletteBG(icon)
  window.seticon(WND_ROULETTE, icon)
  return 1
end

function SetRouletteNPC(icon)
  window.seticon(window.find(WND_ROULETTE, 16923), icon)
  return 1
end

function SetRoulettePrizeItem(Idx, itemID, count)
  if Idx < 0 or 9 < Idx then
    return 0
  end
  local w = window.find(WND_ROULETTE, 16910 + Idx)
  window.seticon(w, game.getitemicon(itemID))
  window.settitle(w, count)
  window.setappdata(w, itemID)
  return 1
end

function OnRouletteClickFreeStart(dwID, dwCmdID, dwParam, pParam)
  game.roulettestart(2)
  return 1
end

function OnRouletteClickStart(dwID, dwCmdID, dwParam, pParam)
  game.roulettestart(1)
  return 1
end

function ChangeRouletteGridSeat(idx)
  local w = window.find(WND_ROULETTE, 16920)
  window.show(w, false)
  if idx < 0 or 9 < idx then
    return 0
  end
  window.seticon(w, 16908 + idx)
  window.show(w, true)
  return 1
end

function OnRouletteLogTooltip(dwID, dwCmdID, dwParam, pParam)
  game.roulettelogtooltip(dwParam, pParam)
  return 1
end

function OnRouletteTooltip(dwID, dwCmdID, dwParam, pParam)
  window.settooltiptext(dwID, game.getstring(window.getappdata(dwID)))
  return 1
end
