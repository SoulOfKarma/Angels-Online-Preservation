WNDID_ACHIMNT_MAIN = 28101
BTN_ACHIMNT_BTN1 = 28103
WND_ACHIMNT_PAGE1 = 28110
WND_CROWN_LIST = 28126
WND_PRESTIGE_LIST = 28136
WNDID_CROWN_GOTONLY = 28120
WNDID_PREST_VALUE1 = 28132
WNDID_PREST_VALUE2 = 28139
WNDID_EQUIP_CROWN = 28131
WNDID_OWN_CROWN_NUM = 28134
WND_ACHIMNT = 0
WND_ACHIMNT_X = -1
WND_ACHIMNT_Y = -1
WND_CROWN_LIST = 28126
WND_ACH_LIST = 28165
AchimntMainPage = 0
ACHIEVEMENT_SELECTED_MAIN_TYPE = 0
ACHIEVEMENT_SELECTED_SUB_TYPE = 0
ACHIEVEMENT_MAIN_RES_ID = 28151
ACHIEVEMENT_SUB_RES_ID = 28155
ACHIEVEMENT_MAIN_SELECTION_RES_ID = 28152
ACHIEVEMENT_SUB_SELECTION_RES_ID = 28156
ACHIEVEMENT_POINTS_RES_ID = 28159
ACHIEVEMENT_ACHLIST_RES_ID = 28165
ACHIEVEMENT_TIP_RES_ID = 28168
ACHIEVEMENT_CONDLIST_RES_ID = 28169

function OnOpenAchiWnd()
  if WND_ACHIMNT == 0 then
    CreateAchimententWnd()
  else
    window.destroy(WND_ACHIMNT)
    WND_ACHIMNT = 0
  end
  return 1
end

function CreateAchimententWnd()
  local Wnd_hd
  if window.isexist(WND_ACHIMNT) then
    window.destroy(WND_ACHIMNT)
    WND_ACHIMNT = 0
    return
  end
  WND_ACHIMNT = window.create(WNDID_ACHIMNT_MAIN, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_ACHIMNT_X or 0 > WND_ACHIMNT_Y then
    window.move(WND_ACHIMNT, SYSTEM_SCREEN_WIDTH / 2 - 380, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_ACHIMNT, WND_ACHIMNT_X, WND_ACHIMNT_Y)
  end
  window.regsetting(WND_ACHIMNT, "WND_ACHIMNT")
  AchimntMainPage = 0
  Wnd_hd = window.find(WND_ACHIMNT, BTN_ACHIMNT_BTN1)
  if Wnd_hd then
    window.setradio(Wnd_hd, 0)
  end
  ChangeAchimntPage(0)
  game.updateachwnd()
  UpdateCrownPage()
  return 1
end

function OnChangeAchimntPage(dwID, dwCmdID, dwParam, pParam)
  local nPage = window.getappdata(dwID)
  ChangeAchimntPage(nPage)
  return 1
end

function ChangeAchimntPage(nPage)
  local wnd_GotOnly = window.find(WND_ACHIMNT, WNDID_CROWN_GOTONLY)
  local wnd, n
  for n = 0, 3 do
    wnd = window.find(WND_ACHIMNT, WND_ACHIMNT_PAGE1 + n)
    if wnd ~= 0 then
      if n == nPage then
        window.show(wnd, true)
        if n == 0 then
          game.updateachwnd()
        elseif n == 1 then
          game.updatecrownwnd(window.ischeck(wnd_GotOnly))
        elseif n == 2 then
          game.updateprestwnd()
        end
      else
        window.show(wnd, false)
      end
    end
  end
  return 1
end

function UpdatePrestigePage()
  if WND_ACHIMNT then
    game.updateprestwnd()
  end
  return 1
end

function UpdateCrownPage()
  local wnd_GotOnly
  if WND_ACHIMNT then
    wnd_GotOnly = window.find(WND_ACHIMNT, WNDID_CROWN_GOTONLY)
    game.updatecrownwnd(window.ischeck(wnd_GotOnly))
  end
  return 1
end

function OnEquipCrown(dwID, dwCmdID, dwParam, pParam)
  game.equipcrown(window.getappdata(dwID))
  return 1
end

function OnClickCrownList(dwID, dwCmdID, dwParam, pParam)
  game.clickcrown(dwParam)
  return 1
end

function OnCloseAchimntWnd(dwID, dwCmdID, dwParam, pParam)
  window.show(window.getparent(dwID), false)
  return 1
end

function AchimntChangeBKPage(nBKPage)
end

function OnAchMainTypePopList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getappdata(Wnd)
  local Wnd_ach = window.create(ACHIEVEMENT_MAIN_SELECTION_RES_ID, Wnd, 0, 0)
  if Wnd_ach ~= nil then
    game.updatemaintypepoplist(Wnd_ach)
  end
  return 1
end

function OnAchSubTypePopList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getappdata(Wnd)
  local Wnd_ach = window.create(ACHIEVEMENT_SUB_SELECTION_RES_ID, Wnd, 0, 0)
  if Wnd_ach ~= nil then
    game.updatesubtypepoplist(Wnd_ach, ACHIEVEMENT_SELECTED_MAIN_TYPE)
  end
  return 1
end

function OnChangeAchMainTypeList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getitemappdata(dwID, dwParam)
  if ACHIEVEMENT_SELECTED_MAIN_TYPE ~= appdata then
    ACHIEVEMENT_SELECTED_MAIN_TYPE = appdata
    ACHIEVEMENT_SELECTED_SUB_TYPE = 0
  end
  window.destroy(dwID)
  game.updateachwnd()
  return 1
end

function OnChangeAchSubTypeList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getitemappdata(dwID, dwParam)
  ACHIEVEMENT_SELECTED_SUB_TYPE = appdata
  window.destroy(dwID)
  game.updateachwnd()
  return 1
end

function UpdateAchievementTip(dwID, dwCmdID, dwParam, pParam)
  game.updateachtip()
  return 1
end
