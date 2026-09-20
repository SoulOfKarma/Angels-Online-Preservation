WND_TOTEM = 0
WND_TOWERBASE = 0
WND_BUILDTOTEM = 0
WND_ROUNDKILLBOARD = 0
WND_HITPARADEWIN = 0
WND_NPCKILLGAME = 0

function CreateTotemWnd()
  if window.isexist(WND_TOTEM) then
    window.destroy(WND_TOTEM)
    WND_TOTEM = 0
  end
  WND_TOTEM = window.create(12700, 0, 0, SYSTEM_HANDLER)
  window.move(WND_TOTEM, SYSTEM_SCREEN_WIDTH - 315, SYSTEM_SCREEN_HEIGHT - 149)
  return 1
end

function CreateTowerbaseWnd()
  if window.isexist(WND_TOWERBASE) then
    window.destroy(WND_TOWERBASE)
    WND_TOWERBASE = 0
    return
  end
  WND_TOWERBASE = window.create(12730, 0, 0, SYSTEM_HANDLER)
  window.move(WND_TOWERBASE, SYSTEM_SCREEN_WIDTH - 315, SYSTEM_SCREEN_HEIGHT - 149)
  return 1
end

function CreateTotemBuildWnd()
  if window.isexist(WND_BUILDTOTEM) then
    window.destroy(WND_BUILDTOTEM)
    WND_BUILDTOTEM = 0
  end
  WND_BUILDTOTEM = window.create(24300, 0, 0, SYSTEM_HANDLER)
  window.move(WND_BUILDTOTEM, SYSTEM_SCREEN_WIDTH - 250, SYSTEM_SCREEN_HEIGHT - 450)
  return 1
end

function OnSetInvestValue(dwID, dwCmdID, dwParam, pParam)
  game.setinvestvalue(window.parent(dwID), true)
  return 1
end

function OnTotemInvestEdit(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, -1)
  game.setinvestvalue(window.parent(dwID), false)
  return 1
end

function OnTotemInvestScroll(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, dwParam)
  game.setinvestvalue(window.parent(dwID), false)
  return 1
end

function OnInvestTotem(dwID, dwCmdID, dwParam, pParam)
  game.toteminvest(window.parent(dwID))
  return 1
end

function OnInvestTotemConfirm(dwID, dwCmdID, dwParam, pParam)
  game.toteminvestconfirm(window.parent(dwID))
  return 1
end

function OnTotemInvestWnd(dwID, dwCmdID, dwParam, pParam)
  game.toteminvestwnd()
  return 1
end

function OnPickUpTower(dwID, dwCmdID, dwParam, pParam)
  game.pickuptower()
  window.destroy(window.parent(dwID))
  return 1
end

function OnTotemSetRebornPoint(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(25, 0)
  window.destroy(window.parent(dwID))
  return 1
end

function CreateRoundKillBoardWnd()
  if window.isexist(WND_ROUNDKILLBOARD) then
    return 1
  end
  WND_ROUNDKILLBOARD = window.create(12750, 0, 0, SYSTEM_HANDLER)
  window.move(WND_ROUNDKILLBOARD, SYSTEM_SCREEN_WIDTH - 170, SYSTEM_SCREEN_HEIGHT - 220)
  return 1
end

function LockPVPShortcut(bLock)
  if bLock then
    window.modifystyle(WND_ROUNDKILLBOARD, wsTransparent, wsMoveable)
  else
    window.modifystyle(WND_ROUNDKILLBOARD, wsMoveable, wsTransparent)
  end
end

function OnLockPVPShortcut(dwID, dwCmdID, dwParam, pParam)
  PVP_SHORTCUT_ISLOCK = window.ischeck(dwID)
  LockPVPShortcut(PVP_SHORTCUT_ISLOCK)
  return 1
end

HITPARADE_DATA_SELECT_MAIN_PAGE = 0
HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE1 = 0
HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE2 = 0
HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE3 = 0
HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE4 = 0
HITPARADE_DATA_SELECTPAGE1_TYPE = 0
HITPARADE_DATA_SELECTPAGE1_ALIGN = 0
HITPARADE_DATA_SELECTPAGE1_PAGE = 0
HITPARADE_DATA_SELECTPAGE2_TYPE = 0
HITPARADE_DATA_SELECTPAGE2_ALIGN = 0
HITPARADE_DATA_SELECTPAGE2_PAGE = 0
HITPARADE_DATA_SELECTPAGE3_TYPE = 0
HITPARADE_DATA_SELECTPAGE3_ALIGN = 0
HITPARADE_DATA_SELECTPAGE3_PAGE = 0
HITPARADE_DATA_SELECTPAGE4_TYPE = 0
HITPARADE_DATA_SELECTPAGE4_ALIGN = 0
HITPARADE_DATA_SELECTPAGE4_PAGE = 0
HITPARADE_DATA_SELECTPAGE5_TYPE = 0
HITPARADE_DATA_SELECTPAGE5_ALIGN = 0
HITPARADE_DATA_SELECTPAGE5_PAGE = 0

function CreateHitParadeWin()
  if window.isexist(WND_HITPARADEWIN) then
    return 1
  end
  if game.isdef("__PAD_CONTROL") == false then
    WND_HITPARADEWIN = window.create(12790, 0, 0, SYSTEM_HANDLER)
  else
    WND_HITPARADEWIN = window.create(12790, 0, wsPopup, SYSTEM_HANDLER)
  end
  local hitparade_x = SYSTEM_SCREEN_WIDTH - 609
  local hitparade_y = SYSTEM_SCREEN_HEIGHT - 475
  window.move(WND_HITPARADEWIN, hitparade_x, hitparade_y)
  HITPARADE_DATA_SELECT_MAIN_PAGE = 0
  window.setradio(window.find(window.find(WND_HITPARADEWIN, 12798), 12801), 0)
  HITPARADE_DATA_SELECTPAGE1_ALIGN = 4
  window.setradio(window.find(window.find(WND_HITPARADEWIN, 12799), 12801), 0)
  HITPARADE_DATA_SELECTPAGE2_ALIGN = 4
  window.setradio(window.find(window.find(WND_HITPARADEWIN, 12800), 12801), 0)
  HITPARADE_DATA_SELECTPAGE3_ALIGN = 4
  if game.isdef("__BATTLEFIELD") == true then
    window.setradio(window.find(window.find(WND_HITPARADEWIN, 12825), 12826), 0)
    HITPARADE_DATA_SELECTPAGE4_ALIGN = 1
    window.setradio(window.find(window.find(WND_HITPARADEWIN, 12830), 12801), 0)
    HITPARADE_DATA_SELECTPAGE5_ALIGN = 4
    HideHitParadeWarAnglePage()
  else
    window.show(window.find(window.find(WND_HITPARADEWIN, 12798), 12828), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12799), 12828), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12800), 12828), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12798), 12831), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12799), 12831), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12800), 12831), false)
  end
  HITPARADE_DATA_SELECTPAGE1_TYPE = 0
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12800), 12807), game.getstring(1805))
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12800), 12814), game.getstring(1805))
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12800), 12812), game.getstring(1816))
  HITPARADE_DATA_SELECTPAGE1_PAGE = 0
  HITPARADE_DATA_SELECTPAGE2_TYPE = 4
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12798), 12807), game.getstring(1809))
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12798), 12814), game.getstring(1809))
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12798), 12812), game.getstring(1817))
  HITPARADE_DATA_SELECTPAGE2_PAGE = 0
  HITPARADE_DATA_SELECTPAGE3_TYPE = 7
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12799), 12807), game.getstring(1812))
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12799), 12814), game.getstring(1812))
  window.settitle(window.find(window.find(WND_HITPARADEWIN, 12799), 12812), game.getstring(1816))
  HITPARADE_DATA_SELECTPAGE3_PAGE = 0
  if game.isdef("__BATTLEFIELD") == true then
    HITPARADE_DATA_SELECTPAGE4_TYPE = 18
    window.settitle(window.find(window.find(WND_HITPARADEWIN, 12825), 12807), game.getstring(2239))
    window.settitle(window.find(window.find(WND_HITPARADEWIN, 12825), 12814), game.getstring(2280))
    window.settitle(window.find(window.find(WND_HITPARADEWIN, 12825), 12812), game.getstring(1816))
    HITPARADE_DATA_SELECTPAGE4_PAGE = 0
    HITPARADE_DATA_SELECTPAGE5_TYPE = 30
    window.settitle(window.find(window.find(WND_HITPARADEWIN, 12830), 12807), game.getstring(2245))
    window.settitle(window.find(window.find(WND_HITPARADEWIN, 12830), 12814), game.getstring(2245))
    window.settitle(window.find(window.find(WND_HITPARADEWIN, 12830), 12812), game.getstring(1816))
    HITPARADE_DATA_SELECTPAGE4_PAGE = 0
  end
  HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE1 = 0
  HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE2 = 0
  HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE3 = 0
  if game.isdef("__BATTLEFIELD") == true then
    HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE4 = 0
    HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE5 = 0
  end
  window.show(window.find(WND_HITPARADEWIN, 12800), true)
  window.show(window.find(WND_HITPARADEWIN, 12799), false)
  window.show(window.find(WND_HITPARADEWIN, 12798), false)
  if game.isdef("__BATTLEFIELD") then
    window.show(window.find(WND_HITPARADEWIN, 12825), false)
    window.show(window.find(WND_HITPARADEWIN, 12830), false)
  end
  game.netcommand2(27, 0, 0)
  SendRequestHitParade(1)
  return 1
end

function HideHitParadeWarAnglePage()
  local hitparade_x = SYSTEM_SCREEN_WIDTH - 609
  local hitparade_y = SYSTEM_SCREEN_HEIGHT - 475
  if game.isdef("__KOREA") == true and game.isdef("__HITPARADE_NO_WARANGEL") == true then
    window.show(window.find(window.find(WND_HITPARADEWIN, 12798), 12828), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12799), 12828), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12800), 12828), false)
    window.show(window.find(window.find(WND_HITPARADEWIN, 12830), 12828), false)
    window.move(window.find(window.find(WND_HITPARADEWIN, 12798), 12831), hitparade_x + 241 + 5, hitparade_y + 332 + 20)
    window.move(window.find(window.find(WND_HITPARADEWIN, 12799), 12831), hitparade_x + 241 + 5, hitparade_y + 332 + 20)
    window.move(window.find(window.find(WND_HITPARADEWIN, 12800), 12831), hitparade_x + 241 + 5, hitparade_y + 332 + 20)
    window.move(window.find(window.find(WND_HITPARADEWIN, 12830), 12832), hitparade_x + 241 + 5, hitparade_y + 332 + 20)
  end
end

function OnHitParadeChangePage1(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wndp = window.parent(Wnd)
  window.show(window.find(Wndp, 12800), true)
  window.show(window.find(Wndp, 12799), false)
  window.show(window.find(Wndp, 12798), false)
  if game.isdef("__BATTLEFIELD") then
    window.show(window.find(Wndp, 12825), false)
    window.show(window.find(Wndp, 12830), false)
  end
  HITPARADE_DATA_SELECT_MAIN_PAGE = 0
  SendRequestHitParade(1)
  return 1
end

function OnHitParadeChangePage2(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wndp = window.parent(Wnd)
  window.show(window.find(Wndp, 12800), false)
  window.show(window.find(Wndp, 12799), false)
  window.show(window.find(Wndp, 12798), true)
  if game.isdef("__BATTLEFIELD") then
    window.show(window.find(Wndp, 12825), false)
    window.show(window.find(Wndp, 12830), false)
  end
  HITPARADE_DATA_SELECT_MAIN_PAGE = 1
  if HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE2 == 0 then
    HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE2 = 0
    SendRequestHitParade(1)
  end
  return 1
end

function OnHitParadeChangePage3(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wndp = window.parent(Wnd)
  window.show(window.find(Wndp, 12800), false)
  window.show(window.find(Wndp, 12799), true)
  window.show(window.find(Wndp, 12798), false)
  if game.isdef("__BATTLEFIELD") then
    window.show(window.find(Wndp, 12825), false)
    window.show(window.find(Wndp, 12830), false)
  end
  HITPARADE_DATA_SELECT_MAIN_PAGE = 2
  if HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE3 == 0 then
    HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE3 = 0
    SendRequestHitParade(1)
  end
  return 1
end

function OnHitParadeChangePage4(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wndp = window.parent(Wnd)
  window.show(window.find(Wndp, 12800), false)
  window.show(window.find(Wndp, 12799), false)
  window.show(window.find(Wndp, 12798), false)
  window.show(window.find(Wndp, 12825), true)
  window.show(window.find(Wndp, 12830), false)
  HITPARADE_DATA_SELECT_MAIN_PAGE = 3
  if HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE4 == 0 then
    HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE4 = 0
    SendRequestHitParade(1)
  end
  return 1
end

function OnHitParadeChangePage5(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wndp = window.parent(Wnd)
  window.show(window.find(Wndp, 12800), false)
  window.show(window.find(Wndp, 12799), false)
  window.show(window.find(Wndp, 12798), false)
  window.show(window.find(Wndp, 12825), false)
  window.show(window.find(Wndp, 12830), true)
  HideHitParadeWarAnglePage()
  HITPARADE_DATA_SELECT_MAIN_PAGE = 4
  if HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE5 == 0 then
    HITPARADE_DATA_SELECT_MAIN_FIRST_PAGE5 = 0
    SendRequestHitParade(1)
  end
  return 1
end

function OnChangeHPSelectAlign(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdataPage = window.getappdata(Wnd)
  local appdata = window.getappdata(dwID)
  if appdataPage == 1 then
    HITPARADE_DATA_SELECTPAGE1_ALIGN = appdata
  end
  if appdataPage == 2 then
    HITPARADE_DATA_SELECTPAGE2_ALIGN = appdata
  end
  if appdataPage == 3 then
    HITPARADE_DATA_SELECTPAGE3_ALIGN = appdata
  end
  if game.isdef("__BATTLEFIELD") then
    if appdataPage == 4 then
      HITPARADE_DATA_SELECTPAGE4_ALIGN = appdata
      if appdata == 1 then
        window.settitle(window.find(Wnd, 12814), game.getstring(2280))
        window.settitle(window.find(Wnd, 12807), game.getstring(2239))
        HITPARADE_DATA_SELECTPAGE4_TYPE = 18
      else
        window.settitle(window.find(Wnd, 12814), game.getstring(2238))
        window.settitle(window.find(Wnd, 12807), game.getstring(2239))
        HITPARADE_DATA_SELECTPAGE4_TYPE = 24
      end
    end
    if appdataPage == 5 then
      HITPARADE_DATA_SELECTPAGE5_ALIGN = appdata
    end
  end
  SendRequestHitParade(1)
  return 1
end

function OnHitParadePopList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getappdata(Wnd)
  local Wnd_hd = window.create(12806, Wnd, 0, 0)
  if appdata == 1 and Wnd_hd ~= nil then
    window.insertitemstrappnum(Wnd_hd, game.getstring(1805), 0, 0)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1806), 0, 1)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1807), 0, 2)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1808), 0, 3)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1937), 0, 11)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1938), 0, 12)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1939), 0, 13)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1940), 0, 14)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1941), 0, 15)
    if game.isdef("__USA") == false then
      if game.isdef("__CARD") == true and game.isdef("__HITPARADE_CARD") == true then
        window.insertitemstrappnum(Wnd_hd, game.getstring(2175), 0, 17)
      end
      if game.isdef("__ACHIEVEMENT") == true then
        window.insertitemstrappnum(Wnd_hd, game.getstring(2912), 0, 37)
      end
    end
    if game.isdef("__FINAL_TOWER") == true then
      window.insertitemstrappnum(Wnd_hd, game.getstring(3197), 0, 38)
      window.insertitemstrappnum(Wnd_hd, game.getstring(3198), 0, 39)
    end
  end
  if appdata == 2 and Wnd_hd ~= nil then
    window.insertitemstrappnum(Wnd_hd, game.getstring(1809), 0, 4)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1810), 0, 5)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1811), 0, 6)
  end
  if appdata == 3 and Wnd_hd ~= nil then
    window.insertitemstrappnum(Wnd_hd, game.getstring(1812), 0, 7)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1813), 0, 8)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1814), 0, 9)
    window.insertitemstrappnum(Wnd_hd, game.getstring(1815), 0, 10)
  end
  if game.isdef("__BATTLEFIELD") then
    if appdata == 4 and Wnd_hd ~= nil then
      if game.isdef("__MALAYSIA") then
        window.insertitemstrappnum(Wnd_hd, game.getstring(2239), 0, 1)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2240), 0, 2)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2241), 0, 3)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2242), 0, 4)
      else
        window.insertitemstrappnum(Wnd_hd, game.getstring(2239), 0, 1)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2240), 0, 2)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2241), 0, 3)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2242), 0, 4)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2243), 0, 5)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2802), 0, 6)
        window.insertitemstrappnum(Wnd_hd, game.getstring(2803), 0, 7)
        window.insertitemstrappnum(Wnd_hd, game.getstring(3300), 0, 8)
        window.insertitemstrappnum(Wnd_hd, game.getstring(3301), 0, 9)
        window.insertitemstrappnum(Wnd_hd, game.getstring(3302), 0, 10)
        window.insertitemstrappnum(Wnd_hd, game.getstring(3303), 0, 11)
        window.insertitemstrappnum(Wnd_hd, game.getstring(3304), 0, 12)
        window.insertitemstrappnum(Wnd_hd, game.getstring(3305), 0, 13)
        window.insertitemstrappnum(Wnd_hd, game.getstring(3306), 0, 14)
        if game.isdef("__JAPAN") == false then
          window.insertitemstrappnum(Wnd_hd, game.getstring(3307), 0, 15)
        end
      end
    end
    if appdata == 5 and Wnd_hd ~= nil then
      window.insertitemstrappnum(Wnd_hd, game.getstring(2245), 0, 30)
    end
  end
  return 1
end

function OnChangeHPTypeList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdataPage = window.getappdata(Wnd)
  local appdata = window.getitemappdata(dwID, dwParam)
  if appdataPage == 1 then
    HITPARADE_DATA_SELECTPAGE1_TYPE = appdata
    window.settitle(window.find(Wnd, 12807), window.getitemtitle(dwID, dwParam))
    if 11 <= appdata and appdata <= 15 then
      window.settitle(window.find(Wnd, 12814), game.getstring(1942))
    else
      window.settitle(window.find(Wnd, 12814), window.getitemtitle(dwID, dwParam))
    end
  end
  if appdataPage == 2 then
    HITPARADE_DATA_SELECTPAGE2_TYPE = appdata
    window.settitle(window.find(Wnd, 12807), window.getitemtitle(dwID, dwParam))
    window.settitle(window.find(Wnd, 12814), window.getitemtitle(dwID, dwParam))
  end
  if appdataPage == 3 then
    HITPARADE_DATA_SELECTPAGE3_TYPE = appdata
    if appdata < 9 then
      window.settitle(window.find(Wnd, 12812), game.getstring(1816))
    else
      window.settitle(window.find(Wnd, 12812), game.getstring(1817))
    end
    window.settitle(window.find(Wnd, 12807), window.getitemtitle(dwID, dwParam))
    window.settitle(window.find(Wnd, 12814), window.getitemtitle(dwID, dwParam))
  end
  if game.isdef("__BATTLEFIELD") then
    if appdataPage == 4 then
      HITPARADE_DATA_SELECTPAGE4_TYPE = appdata
      if HITPARADE_DATA_SELECTPAGE4_ALIGN == 1 then
        window.settitle(window.find(Wnd, 12814), game.getstring(2280))
        if appdata == 1 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 18
        elseif appdata == 2 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 19
        elseif appdata == 3 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 20
        elseif appdata == 4 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 21
        elseif appdata == 5 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 22
        elseif appdata == 6 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 23
        elseif appdata == 7 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 35
        elseif appdata == 8 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 41
        elseif appdata == 9 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 42
        elseif appdata == 10 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 43
        elseif appdata == 11 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 44
        elseif appdata == 12 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 45
        elseif appdata == 13 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 46
        elseif appdata == 14 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 47
        elseif appdata == 15 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 48
        end
      else
        window.settitle(window.find(Wnd, 12814), game.getstring(2238))
        if appdata == 1 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 24
        elseif appdata == 2 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 25
        elseif appdata == 3 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 26
        elseif appdata == 4 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 27
        elseif appdata == 5 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 28
        elseif appdata == 6 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 29
        elseif appdata == 7 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 36
        elseif appdata == 8 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 49
        elseif appdata == 9 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 50
        elseif appdata == 10 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 51
        elseif appdata == 11 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 52
        elseif appdata == 12 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 53
        elseif appdata == 13 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 54
        elseif appdata == 14 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 55
        elseif appdata == 15 then
          HITPARADE_DATA_SELECTPAGE4_TYPE = 56
        end
      end
      window.settitle(window.find(Wnd, 12807), window.getitemtitle(dwID, dwParam))
    end
    if appdataPage == 5 then
      HITPARADE_DATA_SELECTPAGE5_TYPE = appdata
      window.settitle(window.find(Wnd, 12807), window.getitemtitle(dwID, dwParam))
      window.settitle(window.find(Wnd, 12814), window.getitemtitle(dwID, dwParam))
    end
  end
  SendRequestHitParade(1)
  window.destroy(dwID)
  return 1
end

function OnHPChangePage(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdataPage = window.getappdata(Wnd)
  local appdata = window.getappdata(dwID)
  local page = 0
  if appdataPage == 1 then
    page = HITPARADE_DATA_SELECTPAGE1_PAGE
  end
  if appdataPage == 2 then
    page = HITPARADE_DATA_SELECTPAGE2_PAGE
  end
  if appdataPage == 3 then
    page = HITPARADE_DATA_SELECTPAGE3_PAGE
  end
  if game.isdef("__BATTLEFIELD") then
    if appdataPage == 4 then
      page = HITPARADE_DATA_SELECTPAGE4_PAGE
    end
    if appdataPage == 5 then
      page = HITPARADE_DATA_SELECTPAGE5_PAGE
    end
  end
  if appdata == 0 and 0 < page then
    page = page - 1
  end
  if appdata == 1 and page < 4 then
    page = page + 1
  end
  if appdataPage == 1 then
    HITPARADE_DATA_SELECTPAGE1_PAGE = page
  end
  if appdataPage == 2 then
    HITPARADE_DATA_SELECTPAGE2_PAGE = page
  end
  if appdataPage == 3 then
    HITPARADE_DATA_SELECTPAGE3_PAGE = page
  end
  if game.isdef("__BATTLEFIELD") then
    if appdataPage == 4 then
      HITPARADE_DATA_SELECTPAGE4_PAGE = page
    end
    if appdataPage == 5 then
      HITPARADE_DATA_SELECTPAGE5_PAGE = page
    end
  end
  window.settitle(window.find(Wnd, 12815), page + 1 .. "/5")
  SendRequestHitParade(0)
  return 1
end

function SendRequestHitParade(clearpage)
  local listID = 0
  local pageID = 0
  if game.isdef("__ACHIEVEMENT") == true then
    HITPARADE_CHOICE_NUM = 11
  else
    HITPARADE_CHOICE_NUM = 10
  end
  if HITPARADE_DATA_SELECT_MAIN_PAGE == 0 then
    listID = window.find(window.find(WND_HITPARADEWIN, 12800), 12824)
    pageID = window.find(window.find(WND_HITPARADEWIN, 12800), 12815)
    if clearpage == 1 then
      HITPARADE_DATA_SELECTPAGE1_PAGE = 0
      window.settitle(pageID, "1/5")
    end
    game.netcommand2(26, HITPARADE_DATA_SELECTPAGE1_TYPE, HITPARADE_DATA_SELECTPAGE1_ALIGN * HITPARADE_CHOICE_NUM + HITPARADE_DATA_SELECTPAGE1_PAGE)
    game.showhitparadedata()
  end
  if HITPARADE_DATA_SELECT_MAIN_PAGE == 1 then
    listID = window.find(window.find(WND_HITPARADEWIN, 12798), 12824)
    pageID = window.find(window.find(WND_HITPARADEWIN, 12798), 12815)
    if clearpage == 1 then
      HITPARADE_DATA_SELECTPAGE2_PAGE = 0
      window.settitle(pageID, "1/5")
    end
    game.netcommand2(26, HITPARADE_DATA_SELECTPAGE2_TYPE, HITPARADE_DATA_SELECTPAGE2_ALIGN * HITPARADE_CHOICE_NUM + HITPARADE_DATA_SELECTPAGE2_PAGE)
    game.showhitparadedata()
  end
  if HITPARADE_DATA_SELECT_MAIN_PAGE == 2 then
    listID = window.find(window.find(WND_HITPARADEWIN, 12799), 12824)
    pageID = window.find(window.find(WND_HITPARADEWIN, 12799), 12815)
    if clearpage == 1 then
      HITPARADE_DATA_SELECTPAGE3_PAGE = 0
      window.settitle(pageID, "1/5")
    end
    game.netcommand2(26, HITPARADE_DATA_SELECTPAGE3_TYPE, HITPARADE_DATA_SELECTPAGE3_ALIGN * HITPARADE_CHOICE_NUM + HITPARADE_DATA_SELECTPAGE3_PAGE)
    game.showhitparadedata()
  end
  if game.isdef("__BATTLEFIELD") then
    if HITPARADE_DATA_SELECT_MAIN_PAGE == 3 then
      listID = window.find(window.find(WND_HITPARADEWIN, 12825), 12824)
      pageID = window.find(window.find(WND_HITPARADEWIN, 12825), 12815)
      if clearpage == 1 then
        HITPARADE_DATA_SELECTPAGE4_PAGE = 0
        window.settitle(pageID, "1/5")
      end
      game.netcommand2(26, HITPARADE_DATA_SELECTPAGE4_TYPE, 4 * HITPARADE_CHOICE_NUM + HITPARADE_DATA_SELECTPAGE4_PAGE)
      game.showhitparadedata()
    end
    if HITPARADE_DATA_SELECT_MAIN_PAGE == 4 then
      listID = window.find(window.find(WND_HITPARADEWIN, 12830), 12824)
      pageID = window.find(window.find(WND_HITPARADEWIN, 12830), 12815)
      if clearpage == 1 then
        HITPARADE_DATA_SELECTPAGE5_PAGE = 0
        window.settitle(pageID, "1/5")
      end
      game.netcommand2(26, HITPARADE_DATA_SELECTPAGE5_TYPE, HITPARADE_DATA_SELECTPAGE5_ALIGN * HITPARADE_CHOICE_NUM + HITPARADE_DATA_SELECTPAGE5_PAGE)
      game.showhitparadedata()
    end
  end
  return 1
end

function CreateNpcKillGameWnd()
  if window.isexist(WND_NPCKILLGAME) then
    return 1
  end
  WND_NPCKILLGAME = window.create(12900, 0, 0, SYSTEM_HANDLER)
  window.move(WND_NPCKILLGAME, SYSTEM_SCREEN_WIDTH - 205, SYSTEM_SCREEN_HEIGHT - 220)
  return 1
end

ROBOT_DEF_VAR_TEST1 = 1
ROBOT_DEF_VAR_TEST2 = 2

function CreateRobotDataVarTestWnd()
  local wndid = 0
  wndid = window.create(24500, 0, 0, SYSTEM_HANDLER)
  window.move(WND_NPCKILLGAME, SYSTEM_SCREEN_WIDTH - 205, SYSTEM_SCREEN_HEIGHT - 220)
  window.settitle(window.find(wndid, 24502), game.getrobotvar_int(ROBOT_DEF_VAR_TEST1))
  window.setcheck(window.find(wndid, 24503), game.getrobotvar_bool(ROBOT_DEF_VAR_TEST2))
  return 1
end

function OnTestSetRobotVarInt(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_int(ROBOT_DEF_VAR_TEST1, window.gettitle(dwID))
  return 1
end

function OnTestSetRobotVarBool(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    game.setrobotvar_bool(ROBOT_DEF_VAR_TEST2, true)
  else
    game.setrobotvar_bool(ROBOT_DEF_VAR_TEST2, false)
  end
  return 1
end
