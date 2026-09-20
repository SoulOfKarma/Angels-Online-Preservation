WND_FINAL_TOWER = 0

function CreateFinalTowerBoardWnd()
  if window.isexist(WND_FINAL_TOWER) then
    return 1
  end
  WND_FINAL_TOWER = window.create(24761, 0, 0, SYSTEM_HANDLER)
  window.move(WND_FINAL_TOWER, SYSTEM_SCREEN_WIDTH / 2 - 90, 50)
  return 1
end

function DestroyFinalTowerBoardWnd()
  if window.isexist(WND_FINAL_TOWER) then
    window.destroy(WND_FINAL_TOWER)
    WND_FINAL_TOWER = 0
  end
end

function LockFinalTowerWnd(bLock)
  if bLock then
    window.modifystyle(WND_FINAL_TOWER, wsTransparent, wsMoveable)
  else
    window.modifystyle(WND_FINAL_TOWER, wsMoveable, wsTransparent)
  end
end

function OnLockFinalTowerWnd(dwID, dwCmdID, dwParam, pParam)
  WND_FINAL_TOWER_ISLOCK = window.ischeck(dwID)
  LockBattleCrystalShortcut(WND_FINAL_TOWER_ISLOCK)
  return 1
end
