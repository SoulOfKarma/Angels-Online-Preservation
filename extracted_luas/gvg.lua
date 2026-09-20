WND_GVG = 0
WND_GVG_X = -1
WND_GVG_Y = -1
WND_GVG_BATTLEFIELD = 0
WND_GVG_BATTLEFIELD_X = -1
WND_GVG_BATTLEFIELD_Y = -1
WND_GVG_BF_SCORE = 0
WND_GVG_BF_TEAM_MEM_NUM = 0
GVG_WND_RES_ID_PAGE_BATTLEINFO = 25124
GVG_WND_RES_ID_PAGE_GUILDINFO = 25169
GVG_WND_RES_ID_PAGE_HITPARADE = 25161
GVG_WND_RES_ID_PAGE_SHOP = 25192
GVG_WND_RES_ID_PAGE_RULE = 25208
GVG_WND_RES_ID_CHECKIN = 25126
GVG_WND_RES_ID_ATTEND = 25127

function CreateGvGWindow()
  if window.isexist(WND_GVG) then
    window.show(WND_GVG, true)
    window.setforeground(WND_GVG)
    return
  end
  WND_GVG = window.create(25122, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_GVG_X or 0 > WND_GVG_Y then
    window.move(WND_GVG, SYSTEM_SCREEN_WIDTH / 2 - window.width(WND_GVG) / 2, SYSTEM_SCREEN_HEIGHT / 2 - window.height(WND_GVG) / 2)
  else
    window.move(WND_GVG, WND_GVG_X, WND_GVG_Y)
  end
  window.regsetting(WND_GVG, "WND_GVG")
  window.setcheck(window.find(WND_GVG, 25168), true)
  ChangePage(GVG_WND_RES_ID_PAGE_GUILDINFO)
  return 1
end

function OnOpenGvGUI(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_GVG) == false then
    CreateGvGWindow()
  end
  game.guildcommand(13, 0, 0)
  game.netcommand(64)
  return 1
end

function OnCloseGvGUI(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_GVG) then
    window.destroy(WND_GVG)
    WND_GVG = 0
    game.netcommand(65)
  end
  return 1
end

function OnGvGCheckin(dwID, dwCmdID, dwParam, pParam)
  game.gvgcheckin()
  return 1
end

function OnGvGAttend(dwID, dwCmdID, dwParam, pParam)
  game.gvgattend()
  return 1
end

function OnGvGCollectWeekReward(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(66)
  return 1
end

function OnGvGCollectMonthReward(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(67)
  return 1
end

function OnSelectGvGListItem(dwID, dwCmdID, dwParam, pParam)
  game.gvgupdatewindow()
  return 1
end

function OnGvGPage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  ChangePage(appdata)
  return 1
end

function ChangePage(dwPageID)
  local page = window.find(WND_GVG, GVG_WND_RES_ID_PAGE_GUILDINFO)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(WND_GVG, GVG_WND_RES_ID_PAGE_BATTLEINFO)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(WND_GVG, GVG_WND_RES_ID_PAGE_HITPARADE)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(WND_GVG, GVG_WND_RES_ID_PAGE_SHOP)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(WND_GVG, GVG_WND_RES_ID_PAGE_RULE)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(WND_GVG, dwPageID)
  window.show(page, true)
  return 1
end

function OnGvGInfuseMaterial(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getappdata(dwID)
  game.gvginfusematerial(appdata)
  return 1
end

function OnGvGShopIncBuyCount(dwID, dwCmdID, dwParam, pParam)
  game.gvgshopaddbuycount(1)
  return 1
end

function OnGvGShopDecBuyCount(dwID, dwCmdID, dwParam, pParam)
  game.gvgshopaddbuycount(-1)
  return 1
end

function OnGvGShopEditBuyCount(dwID, dwCmdID, dwParam, pParam)
  local num = window.gettitleint(dwID)
  game.gvgshopsetbuycount(num)
  return 1
end

function OnGvGShopClickListItem(dwID, dwCmdID, dwParam, pParam)
  game.gvgshopclicklistitem()
  return 1
end

function OnGvGShopClickBuy(dwID, dwCmdID, dwParam, pParam)
  game.gvgshopclickbuy()
  return 1
end

function OnGvGShopConfirmBuy(dwID, dwCmdID, dwParam, pParam)
  game.gvgshopconfirmbuy()
  return 1
end

function CreateGvGScoreWnd()
  if window.isexist(WND_GVG_BF_SCORE) then
    return 1
  end
  WND_GVG_BF_SCORE = window.create(25150, 0, 0, SYSTEM_HANDLER)
  window.regsetting(WND_GVG_BF_SCORE, "WND_GVG_BF_SCORE")
  window.move(WND_GVG_BF_SCORE, SYSTEM_SCREEN_WIDTH / 2 - window.width(WND_GVG_BF_SCORE) / 2, 80)
  return 1
end

function DestroyGvGScoreWnd()
  if window.isexist(WND_GVG_BF_SCORE) then
    window.destroy(WND_GVG_BF_SCORE)
    WND_GVG_BF_SCORE = 0
  end
  return 1
end

function CreateGvGBattlefieldWnd()
  if window.isexist(WND_GVG_BATTLEFIELD) then
    return 1
  end
  WND_GVG_BATTLEFIELD = window.create(25140, 0, 0, SYSTEM_HANDLER)
  window.regsetting(WND_GVG_BATTLEFIELD, "WND_GVG_BATTLEFIELD")
  window.setbgcolor(WND_GVG_BATTLEFIELD, 50, 50, 50, 50)
  window.move(WND_GVG_BATTLEFIELD, SYSTEM_SCREEN_WIDTH - window.width(WND_GVG_BATTLEFIELD), SYSTEM_SCREEN_HEIGHT / 2)
  return 1
end

function DestroyGvGBattlefieldWnd()
  if window.isexist(WND_GVG_BATTLEFIELD) then
    window.destroy(WND_GVG_BATTLEFIELD)
    WND_GVG_BATTLEFIELD = 0
  end
  return 1
end
