WND_DEAD_OPTION = 0

function ShowDeadOptionWindow(bGhost)
  local w
  if window.isexist(WND_DEAD_OPTION) == false then
    WND_DEAD_OPTION = window.create(380, 0, 0, SYSTEM_HANDLER)
    w = window.find(WND_DEAD_OPTION, 385)
    window.settitle(w, game.getrebornstring())
    window.setradio(w, 0)
    if bGhost == true then
      w = window.find(WND_DEAD_OPTION, 386)
      window.enable(w, false)
    end
    window.move(WND_DEAD_OPTION, (SYSTEM_SCREEN_WIDTH - window.width(WND_DEAD_OPTION)) / 2, (SYSTEM_SCREEN_HEIGHT - window.height(WND_DEAD_OPTION)) / 2)
  end
end

function OnCancelDeadWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function CloseDeadWnd()
  if WND_DEAD_OPTION ~= 0 then
    window.destroy(WND_DEAD_OPTION)
    WND_DEAD_OPTION = 0
  end
end

function OnOkDeadWnd(dwID, dwCmdID, dwParam, pParam)
  local w, sel
  w = window.find(WND_DEAD_OPTION, 385)
  sel = window.getradio(w)
  if sel == 0 then
    game.netcommand(2)
  else
    game.netcommand(3)
    game.addsystemmessage(793)
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnOKReborn(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.netcommand(2, 1)
  return 1
end

function OnCancelReborn(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.netcommand(2, 2)
  return 1
end
