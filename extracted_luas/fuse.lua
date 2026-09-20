WND_FUSE = 0
WND_FUSE_EXPLAIN = 0
WND_FUSE_CONFIRM = 0
WND_FUSE_PET_PREVIEW = 0
WND_FUSE_PET_PREVIEW_RES = 0

function CreatePetPreRes()
  if window.isexist(WND_FUSE_PET_PREVIEW_RES) then
    window.destroy(WND_FUSE_PET_PREVIEW_RES)
    WND_FUSE_PET_PREVIEW_RES = 0
    return
  end
  WND_FUSE_PET_PREVIEW_RES = window.create(15033, 0, 0, SYSTEM_HANDLER)
  local x, y
  x = window.left(WND_FUSE)
  y = window.top(WND_FUSE)
  window.move(WND_FUSE_PET_PREVIEW_RES, x + 20, y + 100)
  game.fusecalcprop(WND_FUSE_PET_PREVIEW_RES, 15038)
  return 1
end

function OnFusePetPreResOK(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(47, 1)
  window.destroy(WND_FUSE_PET_PREVIEW_RES)
  WND_FUSE_PET_PREVIEW_RES = 0
  game.fuseclearpetattrib()
  return 1
end

function OnFusePetResCancel(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_FUSE_PET_PREVIEW_RES) then
    window.destroy(WND_FUSE_PET_PREVIEW_RES)
    WND_FUSE_PET_PREVIEW_RES = 0
    game.netcommand(47, 0)
    return 1
  end
  game.netcommand(47, 0)
  return 1
end

function OnFusePreviewPet(dwID, dwCmdID, dwParam, pParam)
  if game.fuseispettrans() == 0 then
    return 1
  end
  WND_FUSE_PET_PREVIEW = window.create(15028, 0, 0, SYSTEM_HANDLER)
  local x, y
  x = window.left(WND_FUSE)
  y = window.top(WND_FUSE)
  window.move(WND_FUSE_PET_PREVIEW, x + 20, y + 200)
  game.fuseclearpetattrib()
  return 1
end

function OnFusePetPreOK(dwID, dwCmdID, dwParam, pParam)
  if game.fuseconfirm() == 0 then
    return 1
  end
  game.fuseok(1)
  window.destroy(WND_FUSE_PET_PREVIEW)
  WND_FUSE_PET_PREVIEW = 0
  return 1
end

function OnFusePetPreCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_FUSE_PET_PREVIEW)
  WND_FUSE_PET_PREVIEW = 0
  return 1
end

function CreateItemFuseWnd()
  if window.isexist(WND_FUSE) then
    window.destroy(WND_FUSE)
    WND_FUSE = 0
    return
  end
  game.fuseclearwnditem()
  WND_FUSE = window.create(15001, 0, 0, SYSTEM_HANDLER)
  local w = window.find(WND_FUSE, 15004)
  window.setdrop(w, LUA_DROP_TYPE_ALL, 4294967295)
  w = window.find(WND_FUSE, 15005)
  window.setdrop(w, LUA_DROP_TYPE_ALL, 4294967295)
  w = window.find(WND_FUSE, 15006)
  window.setdrop(w, LUA_DROP_TYPE_ALL, 4294967295)
  w = window.find(WND_FUSE, 15007)
  window.setdrop(w, LUA_DROP_TYPE_ALL, 4294967295)
  game.fuseclearpetattrib()
  return 1
end

function OnFuseDrop(dwID, dwCmdID, dwParam, pParam)
  game.fusedrop(dwID, pParam)
  return 1
end

function OnCloseItemFuseWnd_1(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_FUSE_EXPLAIN) then
    window.destroy(WND_FUSE_EXPLAIN)
    WND_FUSE_EXPLAIN = 0
  end
  game.fuseclearwnditem()
  game.fuseclearpetattrib()
  WND_FUSE = 0
  return 1
end

function OnCloseItemFuseWnd(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_FUSE_EXPLAIN) then
    window.destroy(WND_FUSE_EXPLAIN)
    WND_FUSE_EXPLAIN = 0
  end
  if window.isexist(15023) then
    window.destroy(15023)
  end
  game.fuseclearwnditem()
  window.destroy(WND_FUSE)
  WND_FUSE = 0
  game.fuseclearpetattrib()
  return 1
end

function OnFuseOK(dwID, dwCmdID, dwParam, pParam)
  game.fuseok(0)
  window.destroy(WND_FUSE_CONFIRM)
  WND_FUSE_CONFIRM = 0
  game.fuseclearpetattrib()
  return 1
end

function OnFuseConfirm(dwID, dwCmdID, dwParam, pParam)
  if game.fuseconfirm() == 0 then
    return 1
  end
  WND_FUSE_CONFIRM = window.create(15023, 0, 0, SYSTEM_HANDLER)
  local x, y
  x = window.left(WND_FUSE)
  y = window.top(WND_FUSE)
  window.move(WND_FUSE_CONFIRM, x + 20, y + 200)
  game.fusecalcprop(WND_FUSE_CONFIRM, 15026)
  return 1
end

function OnFuseConfirmCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_FUSE_CONFIRM)
  WND_FUSE_CONFIRM = 0
  return 1
end

function OnOpenFuseExplain()
  if window.isexist(WND_FUSE_EXPLAIN) then
    window.destroy(WND_FUSE_EXPLAIN)
    WND_FUSE_EXPLAIN = 0
    return
  end
  WND_FUSE_EXPLAIN = window.create(15041, 0, 0, SYSTEM_HANDLER)
  window.settitle(window.find(WND_FUSE_EXPLAIN, 15042), game.getstring(2783) .. game.getstring(2784) .. game.getstring(2785))
  return 1
end

function OnRClickFuseItem(dwID, dwCmdID, dwParam, pParam)
  game.fusecancelitem(dwCmdID)
  return 1
end
