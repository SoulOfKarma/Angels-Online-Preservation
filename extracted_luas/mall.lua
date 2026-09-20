WND_MALL = 0
WND_MALL_CHECKAGAIN = 0
WND_MALL_X = -1
WND_MALL_Y = -1
MallMainPage = 0
MallSubPage = 0
MALL_MAINPAGE_SPECIAL_JP = 1
MALL_MAINPAGE_FURNITURE_JP = 3
MALL_MAINPAGE_DOLLROBOT_JP = 4
MALL_PAGE_HOUSE = -1
MALL_PAGE_PD = -1
MALL_PAGE_HELP = -1
MALL_PAGE_MY = -1

function CreateMallWnd()
  if game.isdef("__KOREA") then
    return 1
  end
  local Wnd_hd
  if window.isexist(WND_MALL) then
    OnMallClose()
    window.destroy(WND_MALL)
    WND_MALL = 0
    return
  end
  WND_MALL = window.create(12400, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_MALL_X or 0 > WND_MALL_Y then
    window.move(WND_MALL, SYSTEM_SCREEN_WIDTH / 2 - 380, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_MALL, WND_MALL_X, WND_MALL_Y)
  end
  window.regsetting(WND_MALL, "WND_MALL")
  if game.isdef("__MALL_LAYOUT") then
    MallMainPage = 0
    MallSubPage = 0
  elseif game.isdef("__CHINA") then
    if game.isdef("__MY_HOUSE") then
      SetHouseMenu()
    end
    MallMainPage = 1
    MallSubPage = 0
  elseif game.isdef("__JAPAN") then
    SetJPMenu()
    MallMainPage = 6
    MallSubPage = 0
  elseif game.isdef("__USA") then
    SetUSAMenu()
    MallMainPage = 6
    MallSubPage = 0
  elseif game.isdef("__MY_HOUSE") then
    SetHouseMenu()
    MallMainPage = 0
    MallSubPage = 0
  elseif game.isdef("__MALAYSIA") then
    MallMainPage = 0
    MallSubPage = 1
  else
    MallMainPage = 0
    MallSubPage = 0
  end
  if not game.isdef("__MALL_LAYOUT") then
    if game.isdef("__JAPAN") then
      ChangeButtonTextJAPAN()
    elseif game.isdef("__080415MALL") then
      ChangeButtonText()
    end
  end
  if game.isdef("__MILE_MALL") then
    Wnd_hd = window.find(WND_MALL, 12421)
    window.show(Wnd_hd, true)
  end
  if game.isdef("__MALL_EXTRALINK") == false then
    Wnd_hd = window.find(WND_MALL, 12455)
    window.show(Wnd_hd, false)
  end
  MallChangeBKPage(0)
  if game.isdef("__SERVERMALL") then
    game.inititemmall()
  else
    game.setmallpage(MallMainPage, MallSubPage)
  end
  Wnd_hd = window.find(WND_MALL, 12411)
  window.setradio(Wnd_hd, MallMainPage)
  Wnd_hd = window.find(WND_MALL, 12431)
  window.setradio(Wnd_hd, MallSubPage)
  if not game.isdef("__SERVERMALL") then
    game.loadmallmyfavo()
  end
  game.initmallitemwnd()
  return 1
end

function OnMallClose(dwID, dwCmdID, dwParam, pParam)
  if not game.isdef("__SERVERMALL") then
    game.savemallmyfavo()
  end
  return 1
end

function MallChangeMainPage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local Wnd_hd
  MallMainPage = appdata
  MallSubPage = 0
  Wnd_hd = 0
  if game.isdef("__MALL_LAYOUT") then
    if MallMainPage == MALL_PAGE_HELP then
      MallChangeBKPage(1)
      game.setmallpage(MallMainPage, MallSubPage)
    elseif MallMainPage == MALL_PAGE_MY then
      MallChangeBKPage(0)
      game.setmallpage(MallMainPage, MallSubPage)
    elseif MallMainPage == MALL_PAGE_HOUSE then
      MallChangeBKPage(2)
      game.setmallpage(MallMainPage, MallSubPage)
      Wnd_hd = window.find(WND_MALL, 12431)
      game.inimallfitting(MallMainPage)
    elseif MallMainPage == MALL_PAGE_PD then
      MallChangeBKPage(2)
      game.setmallpage(MallMainPage, MallSubPage)
      Wnd_hd = window.find(WND_MALL, 12431)
      game.inimallfitting(MallMainPage)
    else
      MallChangeBKPage(0)
      game.setmallpage(MallMainPage, MallSubPage)
      Wnd_hd = window.find(WND_MALL, 12431)
    end
    window.setradio(Wnd_hd, MallSubPage)
  elseif MallMainPage == 8 then
    MallChangeBKPage(1)
    MallHideSubBtn()
    game.setmallpage(MallMainPage, MallSubPage)
  elseif MallMainPage == 9 then
    MallChangeBKPage(0)
    MallHideSubBtn()
    game.setmallpage(MallMainPage, MallSubPage)
  elseif game.isdef("__MY_HOUSE") and (game.isdef("__JAPAN") == false and MallMainPage == 2 or game.isdef("__JAPAN") == true and MallMainPage == MALL_MAINPAGE_FURNITURE_JP) then
    MallChangeBKPage(2)
    game.setmallpage(MallMainPage, MallSubPage)
    Wnd_hd = window.find(WND_MALL, 12431)
    window.setradio(Wnd_hd, MallSubPage)
    game.inimallfitting(MallMainPage)
  elseif not game.isdef("__080415MALL") and (MallMainPage == 3 or MallMainPage == 4) or game.isdef("__080415MALL") and MallMainPage == 5 then
    MallChangeBKPage(2)
    MallHideSubBtn()
    game.setmallpage(MallMainPage, MallSubPage)
    Wnd_hd = window.find(WND_MALL, 12431)
    window.setradio(Wnd_hd, MallSubPage)
    game.inimallfitting(MallMainPage)
  else
    MallChangeBKPage(0)
    game.setmallpage(MallMainPage, MallSubPage)
    Wnd_hd = window.find(WND_MALL, 12431)
    window.setradio(Wnd_hd, MallSubPage)
  end
  return 1
end

function ChangeButtonText()
  local btn2 = window.find(WND_MALL, 12413)
  local btn3 = window.find(WND_MALL, 12414)
  local btn4 = window.find(WND_MALL, 12415)
  local btn5 = window.find(WND_MALL, 12416)
  if game.isdef("__MY_HOUSE") then
    window.settitle(btn2, game.getstring(2371))
  else
    window.settitle(btn2, game.getstring(2332))
  end
  if game.isdef("__INDONESIA") then
    window.settitle(btn3, game.getstring(1947))
  else
    window.settitle(btn3, game.getstring(2333))
  end
  window.settitle(btn4, game.getstring(2334))
  window.settitle(btn5, game.getstring(2335))
end

function ChangeButtonTextJAPAN()
  local btn3 = window.find(WND_MALL, 12414)
  local btn4 = window.find(WND_MALL, 12415)
  if game.isdef("__MY_HOUSE") then
    window.settitle(btn3, game.getstring(2371))
    window.settitle(btn4, game.getstring(2335))
  end
end

function MallChangeBKPage(nBKPage)
  local wnd
  local bShow = {
    false,
    false,
    false
  }
  bShow[nBKPage + 1] = true
  wnd = window.find(WND_MALL, 12402)
  if wnd ~= 0 then
    window.show(wnd, bShow[1])
  end
  wnd = window.find(WND_MALL, 12403)
  if wnd ~= 0 then
    window.show(wnd, bShow[2])
  end
  wnd = window.find(WND_MALL, 12601)
  if wnd ~= 0 then
    window.show(wnd, bShow[3])
  end
  return 1
end

function MallHideSubBtn()
  local wnd, n
  for n = 12431, 12436 do
    wnd = window.find(WND_MALL, n)
    if wnd ~= 0 then
      window.show(wnd, false)
    end
  end
  return 1
end

function MallChangeSubPage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  if game.isdef("__MALL_LAYOUT") then
    MallSubPage = appdata
    if game.isdef("__MY_HOUSE") and MallMainPage == MALL_PAGE_HOUSE then
      game.resetmallfittingfurniture()
    end
  elseif game.isdef("__JAPAN") then
    MallSubPage = appdata
    if MallMainPage == MALL_MAINPAGE_SPECIAL_JP then
      if appdata == 2 then
        MallSubPage = 14
      end
    elseif MallMainPage == MALL_MAINPAGE_FURNITURE_JP then
      if game.isdef("__MY_HOUSE") then
        game.resetmallfittingfurniture()
      end
    elseif MallMainPage == MALL_MAINPAGE_DOLLROBOT_JP then
      if appdata == 2 then
        MallSubPage = -7
      elseif appdata == 3 then
        MallSubPage = -6
      end
    end
  elseif game.isdef("__080415MALL") then
    if MallMainPage == 1 and appdata == 1 then
      if game.isdef("__USA") then
        MallSubPage = -3
      else
        MallSubPage = 3
      end
    elseif game.isdef("__MY_HOUSE") and MallMainPage == 1 and appdata == 2 then
      if game.isdef("__USA") then
        MallSubPage = 11
      else
        MallSubPage = 14
      end
    elseif MallMainPage == 5 and appdata == 2 then
      MallSubPage = -7
    elseif MallMainPage == 5 and appdata == 3 then
      MallSubPage = 16
    else
      if game.isdef("__MY_HOUSE") and MallMainPage == 2 then
        game.resetmallfittingfurniture()
      end
      MallSubPage = appdata
    end
  else
    MallSubPage = appdata
  end
  game.setmallpage(MallMainPage, MallSubPage)
  return 1
end

function MallBuyCheck(dwID, dwCmdID, dwParam, pParam)
  if game.dosafeverify(5) ~= 1 then
    return 1
  end
  local list
  if game.isdef("__MALL_LAYOUT") then
    if MallMainPage == MALL_PAGE_HOUSE or MallMainPage == MALL_PAGE_PD then
      list = 12602
    else
      list = 12404
    end
  else
    list = 12404
    if game.isdef("__MY_HOUSE") and game.isdef("__JAPAN") == false and MallMainPage == 2 or game.isdef("__MY_HOUSE") and game.isdef("__JAPAN") == true and MallMainPage == MALL_MAINPAGE_FURNITURE_JP or game.isdef("__080415MALL") and MallMainPage == 5 or not game.isdef("__080415MALL") and (MallMainPage == 3 or MallMainPage == 4) then
      list = 12602
    end
  end
  local Wnd_hd = window.find(WND_MALL, list)
  local Wnd_Button = window.find(WND_MALL, 12441)
  if window.getlistcheckitem(Wnd_hd) == -1 then
    local Wnd = window.create(12537, Wnd_Button, 0, 0)
  else
    if game.isdef("__MILE_MALL") and not game.checkmilemall() then
      return 1
    end
    local Wnd = window.create(12530, Wnd_Button, 0, 0)
  end
  return 1
end

function MallBuy(dwID, dwCmdID, dwParam, pParam)
  game.mallbuy()
  window.destroy(window.parent(dwID))
  return 1
end

function MallNoService(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.create(12534, dwID, 0, 0)
  return 1
end

function OnGetMallBagItem(dwID, dwCmdID, dwParam, pParam)
  local slot = dwCmdID - 12542
  game.getmallbagitem(dwID, slot)
  return 1
end

function OnDragMallBagItem(dwID, dwCmdID, dwParam, pParam)
  game.dragmallitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropMallBagItem(dwID, dwCmdID, dwParam, pParam)
  game.dropmallitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnMallGiveCheck(dwID, dwCmdID, dwParam, pParam)
  local list
  if game.isdef("__MALL_LAYOUT") then
    if MallMainPage == MALL_PAGE_HOUSE or MallMainPage == MALL_PAGE_PD then
      list = 12602
    else
      list = 12404
    end
  else
    list = 12404
    if game.isdef("__MY_HOUSE") and game.isdef("__JAPAN") == false and MallMainPage == 2 or game.isdef("__MY_HOUSE") and game.isdef("__JAPAN") == true and MallMainPage == MALL_MAINPAGE_FURNITURE_JP or game.isdef("__080415MALL") and MallMainPage == 5 or not game.isdef("__080415MALL") and (MallMainPage == 3 or MallMainPage == 4) then
      list = 12602
    end
  end
  local Wnd_hd = window.find(WND_MALL, list)
  local Wnd_Button = window.find(WND_MALL, 12442)
  if window.getlistcheckitem(Wnd_hd) == -1 then
    local Wnd = window.create(12537, Wnd_Button, 0, 0)
  else
    if window.isexist(WND_MALL_CHECKAGAIN) then
      window.destroy(WND_MALL_CHECKAGAIN)
      WND_MALL_CHECKAGAIN = 0
    end
    if game.isdef("__MILE_MALL") and not game.checkmilemall() then
      return 1
    end
    WND_MALL_CHECKAGAIN = window.create(12560, Wnd_Button, 0, 0)
  end
  return 1
end

function OnMallGiveCheckAgain(dwID, dwCmdID, dwParam, pParam)
  if game.dosafeverify(11) ~= 1 then
    return 1
  end
  local Wnd_Button = window.find(WND_MALL, 12442)
  if game.mallgivenamecheck() == false then
    local Wnd = window.create(12569, Wnd_Button, 0, 0)
  else
    game.mallgivecheckagain(Wnd_Button)
  end
  window.destroy(WND_MALL_CHECKAGAIN)
  return 1
end

function OnMallGive(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.mallgive()
  return 1
end

function OnMallAddMyFavorites(dwID, dwCmdID, dwParam, pParam)
  local list
  if game.isdef("__MALL_LAYOUT") then
    if MallMainPage == MALL_PAGE_HOUSE or MallMainPage == MALL_PAGE_PD then
      list = 12602
    else
      list = 12404
    end
  else
    list = 12404
    if game.isdef("__MY_HOUSE") and game.isdef("__JAPAN") == false and MallMainPage == 2 or game.isdef("__MY_HOUSE") and game.isdef("__JAPAN") == true and MallMainPage == MALL_MAINPAGE_FURNITURE_JP or game.isdef("__080415MALL") and MallMainPage == 5 or not game.isdef("__080415MALL") and (MallMainPage == 3 or MallMainPage == 4) then
      list = 12602
    end
  end
  local Wnd_hd = window.find(WND_MALL, list)
  local Wnd_Button = window.find(WND_MALL, 12443)
  if window.getlistcheckitem(Wnd_hd) == -1 then
    local Wnd = window.create(12537, Wnd_Button, 0, 0)
  else
    game.malladdmyfavorites()
  end
  return 1
end

function OnMalldelMyFavorites(dwID, dwCmdID, dwParam, pParam)
  game.malldelmyfavorites()
  return 1
end

function OnResetMallFitting(dwID, dwCmdID, dwParam, pParam)
  game.resetmallfitting()
  return 1
end

function OnTurnMallFitting_1(dwID, dwCmdID, dwParam, pParam)
  local nFurniturePage
  if game.isdef("__MALL_LAYOUT") then
    nFurniturePage = MALL_PAGE_HOUSE
  elseif game.isdef("__JAPAN") then
    nFurniturePage = MALL_MAINPAGE_FURNITURE_JP
  else
    nFurniturePage = 2
  end
  if MallMainPage == nFurniturePage then
    game.mallfittingmirror(false)
  else
    game.turnmallfitting(-32)
  end
  return 1
end

function OnTurnMallFitting_2(dwID, dwCmdID, dwParam, pParam)
  local nFurniturePage
  if game.isdef("__MALL_LAYOUT") then
    nFurniturePage = MALL_PAGE_HOUSE
  elseif game.isdef("__JAPAN") then
    nFurniturePage = MALL_MAINPAGE_FURNITURE_JP
  else
    nFurniturePage = 2
  end
  if MallMainPage == nFurniturePage then
    game.mallfittingmirror(true)
  else
    game.turnmallfitting(32)
  end
  return 1
end

function OnMallFitting(dwID, dwCmdID, dwParam, pParam)
  game.mallfitting()
  return 1
end

function OnMallFittingList(dwID, dwCmdID, dwParam, pParam)
  game.mallfittingchecksex()
  return 1
end

function SetJPMenu()
  local b1, b2, b3, b4, b5, b6, b7, bx, by
  b7 = window.find(WND_MALL, 12417)
  bx = window.left(b7)
  by = window.top(b7)
  b1 = window.find(WND_MALL, 12411)
  window.move(b7, window.left(b1), by)
  b2 = window.find(WND_MALL, 12412)
  window.move(b1, window.left(b2), by)
  b3 = window.find(WND_MALL, 12413)
  window.move(b2, window.left(b3), by)
  b4 = window.find(WND_MALL, 12414)
  window.move(b3, window.left(b4), by)
  b5 = window.find(WND_MALL, 12415)
  window.move(b4, window.left(b5), by)
  b6 = window.find(WND_MALL, 12416)
  window.move(b5, window.left(b6), by)
  window.move(b6, bx, by)
end

function SetUSAMenu()
  local b1, b2, b3, b4, b5, b6, b7, b8, b8x, by, b7x, b4x, b6x
  b1 = window.find(WND_MALL, 12411)
  b2 = window.find(WND_MALL, 12412)
  b3 = window.find(WND_MALL, 12413)
  b4 = window.find(WND_MALL, 12414)
  b5 = window.find(WND_MALL, 12415)
  b6 = window.find(WND_MALL, 12416)
  b7 = window.find(WND_MALL, 12417)
  b8 = window.find(WND_MALL, 12418)
  b4x = window.left(b4)
  b6x = window.left(b6)
  b7x = window.left(b7)
  b8x = window.left(b8)
  by = window.top(b8)
  window.move(b7, window.left(b1), by)
  window.move(b8, window.left(b2), by)
  window.move(b4, window.left(b3), by)
  window.move(b2, b4x, by)
  window.move(b1, b6x, by)
  window.move(b3, b7x, by)
  window.move(b6, b8x, by)
end

function SetHouseMenu()
  local b3, b4, b5, b6, by, b3x, b4x, b5x, b6x
  b3 = window.find(WND_MALL, 12413)
  b4 = window.find(WND_MALL, 12414)
  b5 = window.find(WND_MALL, 12415)
  b6 = window.find(WND_MALL, 12416)
  b3x = window.left(b6)
  b4x = window.left(b3)
  b5x = window.left(b4)
  b6x = window.left(b5)
  by = window.top(b3)
  window.move(b3, b3x, by)
  window.move(b4, b4x, by)
  window.move(b5, b5x, by)
  window.move(b6, b6x, by)
end

function OnLinkWebSite(dwID, dwCmdID, dwParam, pParam)
  if game.isdef("__MALL_EXTRALINK") then
    game.mallextralink()
  end
  return 1
end
