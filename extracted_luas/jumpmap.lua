WNDID_JUMPMAP_MAIN = 28351
WNDID_JUMPMAPCLASS_CURRENT = 28382
WNDID_JUMPMAPCLASS_POPLIST = 28383
WND_JUMPMAP_MAIN = 0
WND_JUMPMAP_MAIN_X = 0
WND_JUMPMAP_MAIN_Y = 0
WND_JUMPMAPCLASS_SELECTED = 1

function CreateJumpMapWnd()
  if window.isexist(WND_JUMPMAP_MAIN) then
    window.destroy(WND_JUMPMAP_MAIN)
    WND_JUMPMAP_MAIN = 0
    return
  end
  WND_JUMPMAP_MAIN = window.create(WNDID_JUMPMAP_MAIN, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_JUMPMAP_MAIN_X or 0 > WND_JUMPMAP_MAIN_Y then
    window.move(WND_JUMPMAP_MAIN, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_JUMPMAP_MAIN, WND_JUMPMAP_MAIN_X, WND_JUMPMAP_MAIN_Y)
  end
  window.regsetting(WND_JUMPMAP_MAIN, "WND_JUMPMAP_MAIN")
  return 1
end

function OnOpenJumpMapWnd()
  CreateJumpMapWnd()
  game.updatejumpmapcurrclass(WND_JUMPMAPCLASS_SELECTED)
end

function DestroyJumpMapWnd()
  WND_JUMPMAP_MAIN = 0
  return 1
end

function OnGotoJumpMap(dwID, dwCmdID, dwParam, pParam)
  game.gotojumpmap(dwCmdID)
  return 1
end

function OnJumpMapClassPopList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_Awd = window.create(WNDID_JUMPMAPCLASS_POPLIST, Wnd, 0, 0)
  if Wnd_Awd ~= nil then
    game.jumpmapclasspoplist(Wnd_Awd)
  end
  return 1
end

function OnChangeJumpMapClass(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getitemappdata(dwID, dwParam)
  WND_JUMPMAPCLASS_SELECTED = appdata
  window.destroy(dwID)
  game.updatejumpmapcurrclass(WND_JUMPMAPCLASS_SELECTED)
  return 1
end

function OnClickJumpMapTreeItem(dwID, dwCmdID, dwParam, pParam)
  return 1
end
