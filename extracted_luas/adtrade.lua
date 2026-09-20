WND_ADTRADE = 0
WND_ADTRADE_PAGE = 0
WND_ITEMTYPE = 0
WND_SELECTLV = 0
ITEM_BUY_TYPE = 0
PLAYER_BUY_TYPE = 0

function OnADTrade_ChaPage_Item(dwID, dwCmdID, dwParam, pParam)
  local WndADTrade = window.parent(dwID)
  local ItemPage = window.find(WndADTrade, 3511)
  local PlayerPage = window.find(WndADTrade, 3551)
  window.show(ItemPage, true)
  window.show(PlayerPage, false)
  local Btn_ItemPage = window.find(WndADTrade, 3502)
  local Btn_PlayerPage = window.find(WndADTrade, 3503)
  window.seticon(Btn_ItemPage, 3085)
  window.seticon(Btn_PlayerPage, 3084)
  WND_ADTRADE_PAGE = 0
  return 1
end

function OnADTrade_ChaPage_Player(dwID, dwCmdID, dwParam, pParam)
  local WndADTrade = window.parent(dwID)
  local ItemPage = window.find(WndADTrade, 3511)
  local PlayerPage = window.find(WndADTrade, 3551)
  window.show(ItemPage, false)
  window.show(PlayerPage, true)
  local Btn_ItemPage = window.find(WndADTrade, 3502)
  local Btn_PlayerPage = window.find(WndADTrade, 3503)
  window.seticon(Btn_ItemPage, 3084)
  window.seticon(Btn_PlayerPage, 3085)
  WND_ADTRADE_PAGE = 1
  return 1
end

function OnADTrade_Item_BuyType(dwID, dwCmdID, dwParam, pParam)
  ITEM_BUY_TYPE = window.getappdata(dwID)
  w = window.find(WND_ADTRADE, 3520)
  window.setradio(w, ITEM_BUY_TYPE)
  return 1
end

function OnADTrade_Player_BuyType(dwID, dwCmdID, dwParam, pParam)
  PLAYER_BUY_TYPE = window.getappdata(dwID)
  w = window.find(WND_ADTRADE, 3571)
  window.setradio(w, PLAYER_BUY_TYPE)
  return 1
end

function OnADTrade_Item_Search(dwID, dwCmdID, dwParam, pParam)
  if ITEM_BUY_TYPE == 0 then
    window.seticon(window.parent(dwID), 3511)
  else
    window.seticon(window.parent(dwID), 3512)
  end
  return 1
end

function OnADTrade_Player_Search(dwID, dwCmdID, dwParam, pParam)
  if PLAYER_BUY_TYPE == 0 then
    window.seticon(window.parent(dwID), 3551)
  else
    window.seticon(window.parent(dwID), 3552)
  end
  return 1
end

function OnADTrade_Item_ItemType(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_ITEMTYPE) then
    return 1
  end
  WND_ITEMTYPE = window.create(3581, window.parent(dwID), 0, 0)
  local list = window.find(WND_ITEMTYPE, 3582)
  for i = 231, 263 do
    window.insertitemstr(list, game.getstring(i), 0)
  end
  return 1
end

function OnADTrade_Item_SelectLV(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_SELECTLV) then
    return 1
  end
  WND_SELECTLV = window.create(3586, window.parent(dwID), 0, 0)
  local list = window.find(WND_SELECTLV, 3587)
  for i = 271, 280 do
    window.insertitemstr(list, game.getstring(i), 0)
  end
  return 1
end

function OnADTrade_SelectItemType(dwID, dwCmdID, dwParam, pParam)
  game.adtradeselectchange(dwParam, window.parent(window.parent(dwID)), 3524)
  window.destroy(window.parent(dwID))
  return 1
end

function OnADTrade_SelectLV(dwID, dwCmdID, dwParam, pParam)
  game.adtradeselectchange(dwParam, window.parent(window.parent(dwID)), 3527)
  window.destroy(window.parent(dwID))
  return 1
end
