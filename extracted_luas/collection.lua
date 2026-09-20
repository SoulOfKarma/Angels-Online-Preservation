WNDID_CLTN_MAIN = 28202
WNDID_CLTN_DROP = 28240
WNDID_CLTN_BOOK = 28206
WNDID_CLTN_AWD = 28207
WNDID_CLTN_TEXT = 28208
WNDID_CLTN_BKLIST = 28231
WNDID_CLTN_AWDLIST = 28232
WNDID_CLTN_TYPE_SCORE = 28251
WNDID_CLTN_TOTAL_SCORE = 28264
WNDID_CLTN_SEND = 28250
WNDID_CLTN_AWD_SHOW_TYPE = 28280
WNDID_CLTN_AWD_SELECT = 28281
WNDID_CLTN_P1_BTN = 28210
WNDID_CLTN_P1_TYPE = 28234
WNDID_CLTN_P1_TYPE_SCORE = 28235
WNDID_CLTN_P1_TOTAL = 28237
WNDID_CLTN_DROP = 28240
WND_CLTN_AWD_TYPE = -1
WND_CLTN_BTN = 0
WND_CLTN = 0
WND_CLTN_CONFIRM = 0
WND_CLTN_BUY = 0
WND_CLTN_POPLIST = 0
WND_CLTN_X = -1
WND_CLTN_Y = -1
CLTN_System = 0
CLTN_MainPage = 0
CLTN_SubPage = 0

function OnOpenCLTNWnd()
  game.cltncancelitem(WNDID_CLTN_DROP)
  CreateCLTNWnd()
  game.opencollectionbook()
  return 1
end

function CreateCLTNWnd()
  local Wnd_hd, WND_text, wnd_BTN3
  if window.isexist(WND_CLTN) then
    window.destroy(WND_CLTN)
    WND_CLTN = 0
    return
  end
  WND_CLTN = window.create(WNDID_CLTN_MAIN, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_CLTN_X or 0 > WND_CLTN_Y then
    window.move(WND_CLTN, SYSTEM_SCREEN_WIDTH / 2 - 380, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_CLTN, WND_CLTN_X, WND_CLTN_Y)
  end
  window.regsetting(WND_CLTN, "WND_CLTN")
  CLTN_MainPage = 0
  CLTN_SubPage = 0
  wnd_BTN3 = window.find(WND_CLTN, 28203)
  window.setradio(wnd_BTN3, CLTN_SubPage)
  CLTNChangeMainPage(CLTN_MainPage)
  local w = window.find(WND_CLTN, WNDID_CLTN_DROP)
  window.setdrop(w, LUA_DROP_TYPE_ALL, 4294967295)
  window.enable(window.find(WND_CLTN, WNDID_CLTN_SEND), false)
  CLTNSystem(CLTN_System)
  return 1
end

function CloseCltnWnd()
  if window.isexist(WND_CLTN) then
    window.destroy(WND_CLTN)
    WND_CLTN = 0
    return
  end
end

function ArrangeBTN()
  local i, index, Wnd
  for i = 28210, 28217 do
    Wnd = window.find(WND_CLTN, i)
    if window.isexist(Wnd) then
      index = i - 28210
      window.moveoffset(Wnd, index * 71, 0)
    end
  end
  for i = 28241, 28248 do
    Wnd = window.find(WND_CLTN, i)
    if window.isexist(Wnd) then
      index = i - 28241 + 1
      window.moveoffset(Wnd, index * 71, 0)
    end
  end
  for i = 28251, 28258 do
    Wnd = window.find(WND_CLTN, i)
    if window.isexist(Wnd) then
      index = i - 28251 + 1
      window.moveoffset(Wnd, index * 71, 19)
    end
  end
  return 1
end

function OnListCLTN()
  game.listcltn()
  return 1
end

function CLTNSetBtnTitle(dwMainPage)
  local i, wnd_sub, wnd_LV, wnd_SlotName, sz
  for i = 0, 2 do
    wnd_sub = window.find(WND_CLTN, 28221 + i)
    if dwMainPage == 5 then
      window.settitle(wnd_sub, game.getstring(2988 + i))
    else
      window.settitle(wnd_sub, game.getstring(2987 + i))
    end
  end
  wnd_sub = window.find(WND_CLTN, 28223)
  if CLTN_MainPage == 5 then
    window.show(wnd_sub, false)
  else
    window.show(wnd_sub, true)
  end
  wnd_LV = window.find(WND_CLTN, 28225)
  wnd_SlotName = window.find(WND_CLTN, 28226)
  wnd_Style = window.find(WND_CLTN, 28220)
  if CLTN_MainPage == 7 then
    window.show(wnd_Style, true)
    window.show(wnd_LV, false)
    window.show(wnd_SlotName, false)
    wnd_SlotName = window.find(WND_CLTN, 28227)
    window.settitle(wnd_SlotName, game.getstring(853))
    wnd_SlotName = window.find(WND_CLTN, 28228)
    window.settitle(wnd_SlotName, game.getstring(854))
    wnd_SlotName = window.find(WND_CLTN, 28229)
    window.settitle(wnd_SlotName, game.getstring(851))
    wnd_SlotName = window.find(WND_CLTN, 28230)
    window.settitle(wnd_SlotName, game.getstring(237))
  else
    window.show(wnd_Style, false)
    window.show(wnd_LV, true)
    window.show(wnd_SlotName, true)
    window.settitle(wnd_LV, game.getstring(2990))
    for i = 1, 5 do
      wnd_SlotName = window.find(WND_CLTN, 28225 + i)
      window.settitle(wnd_SlotName, game.getstring(2992) .. 0 .. i)
    end
  end
  return 1
end

function OnCLTNChangeMainPage(dwID, dwCmdID, dwParam, pParam)
  local dwMainPage = window.getappdata(dwID)
  if dwMainPage < 0 or CLTN_MainPage >= 8 then
    CLTN_MainPage = 0
  else
    CLTN_MainPage = dwMainPage
  end
  CLTNChangeMainPage()
  return 1
end

function CLTNChangeMainPage()
  CLTNSetBtnTitle(CLTN_MainPage)
  CLTNChangePageContent()
  return 1
end

function OnCLTNChangeSubPage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  CLTN_SubPage = appdata
  CLTNChangePageContent()
  return 1
end

function CLTNChangePageContent()
  local wnd = window.find(WND_CLTN, 28231)
  local wnd_BTN = window.find(WND_CLTN, 28210)
  local wnd_BTN2 = window.find(WND_CLTN, 28221)
  local wnd_CLTN_BG = window.find(WND_CLTN, 28206)
  if CLTN_MainPage < 0 or CLTN_MainPage >= 8 then
    CLTN_MainPage = 0
  end
  if 0 > CLTN_SubPage or CLTN_SubPage > 2 then
    CLTN_SubPage = 0
  end
  if CLTN_MainPage == 5 and CLTN_SubPage > 1 then
    CLTN_SubPage = 1
  end
  if wnd ~= 0 then
    window.setradio(wnd_BTN, CLTN_MainPage)
    window.setradio(wnd_BTN2, CLTN_SubPage)
    if CLTN_MainPage == 7 then
      window.seticon(wnd_CLTN_BG, 27103)
    else
      window.seticon(wnd_CLTN_BG, 27102)
    end
    game.changecltnpage()
  end
  return 1
end

function OnCLTNSystem(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  CLTNSystem(appdata)
  return 1
end

function CLTNSystem(appdata)
  local wnd, i
  local ShowWnd = 28206 + appdata
  for i = 28206, 28208 do
    wnd = window.find(WND_CLTN, i)
    if i == ShowWnd then
      window.show(wnd, true)
      if i == 28207 then
        UpdateCltnAwdPage()
      end
    else
      window.show(wnd, false)
    end
  end
  return 1
end

function UpdateCltnAwdPage()
  if WND_CLTN then
    game.updatecltnawdwnd(WND_CLTN_AWD_TYPE)
  end
  return 1
end

function OnCltnAwdPopList(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_Awd = window.create(WNDID_CLTN_AWD_SELECT, Wnd, 0, 0)
  if Wnd_Awd ~= nil then
    game.cltnpoplist(Wnd_Awd)
  end
  return 1
end

function OnChangeCltnAwdType(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getitemappdata(dwID, dwParam)
  WND_CLTN_AWD_TYPE = appdata
  window.destroy(dwID)
  game.updatecltnawdwnd(WND_CLTN_AWD_TYPE)
  return 1
end

function OnCLTNDrop(dwID, dwCmdID, dwParam, pParam)
  local wnd = window.find(WND_CLTN, 28231)
  local wnd_send = window.find(WND_CLTN, WNDID_CLTN_SEND)
  game.cltncancelitem(WNDID_CLTN_DROP)
  window.enable(wnd_send, false)
  game.cltndrop(dwID, pParam)
  return 1
end

function OnRClickCLTNItem(dwID, dwCmdID, dwParam, pParam)
  game.cltncancelitem(WNDID_CLTN_DROP)
  window.enable(window.find(WND_CLTN, WNDID_CLTN_SEND), false)
  return 1
end

function OnCltnConfirm(dwID, dwCmdID, dwParam, pParam)
  WND_CLTN_CONFIRM = window.create(28271, 0, 0, SYSTEM_HANDLER)
  local x, y
  x = window.left(WND_CLTN)
  y = window.top(WND_CLTN)
  window.move(WND_CLTN_CONFIRM, x + 220, y + 150)
  return 1
end

function OnSendCollect()
  game.sendcollect()
  window.destroy(WND_CLTN_CONFIRM)
  WND_CLTN_CONFIRM = 0
  game.cltncancelitem(WNDID_CLTN_DROP)
  window.enable(window.find(WND_CLTN, WNDID_CLTN_SEND), false)
  return 1
end

function OnCltnConfirmCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_CLTN_CONFIRM)
  WND_CLTN_CONFIRM = 0
  return 1
end

function OnBuyCltnSlot()
  WND_CLTN_BUY = window.create(28276, 0, 0, SYSTEM_HANDLER)
  local x, y
  x = window.left(WND_CLTN)
  y = window.top(WND_CLTN)
  window.move(WND_CLTN_BUY, x + 220, y + 150)
  return 1
end

function OnBuyCltnSlot_OK(dwID, dwCmdID, dwParam, pParam)
  game.buycltnslot(CLTN_MainPage, CLTN_SubPage)
  window.destroy(WND_CLTN_BUY)
  WND_CLTN_BUY = 0
  return 1
end

function OnBuyCltnSlot_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_CLTN_BUY)
  WND_CLTN_BUY = 0
  return 1
end
