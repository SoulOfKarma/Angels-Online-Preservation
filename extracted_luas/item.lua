WND_ITEM = 0
WND_PACKAGE = 0
WND_TRADE = 0
WND_EQUIP = 0
WND_SALE = 0
WND_MONEYADIUST = 0
SALEPAGE_SALE = 0
SALEPAGE_BUY = 0
WND_PACKAGE_X = -1
WND_PACKAGE_Y = -1
WND_ITEM_X = -1
WND_ITEM_Y = -1
WND_TRADE_X = -1
WND_TRADE_Y = -1
WND_EQUIP_X = -1
WND_EQUIP_Y = -1
WND_SALE_X = -1
WND_SALE_Y = -1
WND_COMPOUNDBUFFWND = 0
ITEM_CHAR = 1
ITEM_STORAGE = 2
ITEM_CUR_SLOT = -1
ITEM_TO_SLOT = -1
RES_DESTROY_SLOT = -1

function CreateItemWndAndPackageWnd()
  if window.isexist(WND_ITEM) or window.isexist(WND_PACKAGE) then
    window.destroy(WND_ITEM)
    WND_ITEM = 0
    window.destroy(WND_PACKAGE)
    WND_PACKAGE = 0
  else
    CreateItemWnd()
    CreatePackageWnd()
  end
  return 1
end

function CreateItemWnd()
  if window.isexist(WND_ITEM) then
    window.destroy(WND_ITEM)
    WND_ITEM = 0
    return
  end
  WND_ITEM = window.create(3031, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_ITEM_X or 0 > WND_ITEM_Y then
    window.move(WND_ITEM, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_ITEM, WND_ITEM_X, WND_ITEM_Y)
  end
  game.inititemwnd(WND_ITEM, 0)
  window.regsetting(WND_ITEM, "WND_ITEM")
  if window.isexist(WND_TRADE) then
    window.enable(window.find(WND_ITEM, 3039), false)
  end
  return 1
end

function OnGiveMoney_Decrease10(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnGiveMoney_Decrease1(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnGiveMoney_Increase1(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnGiveMoney_Increase10(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnGiveMoney_Ok(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_MONEYADIUST)
  WND_MONEYADIUST = 0
  return 1
end

function OnGiveMoney_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_MONEYADIUST)
  WND_MONEYADIUST = 0
  return 1
end

function OnCreateDestroyItem(dwID)
  parent = window.parent(dwID)
  w = window.create(3051, window.parent(dwID), 0, 0)
  window.move(w, window.left(parent) + (window.width(parent) - window.width(w)) / 2, window.top(parent) + (window.height(parent) - window.height(w)) / 2)
end

function OnDestroyItem(dwID, dwCmdID, dwParam, pParam)
  local w, parent, dwID, dwType, dwSet
  dwID, dwType, dwSet, RES_DESTROY_SLOT, nSlot = game.getdropdata(pParam)
  if RES_DESTROY_SLOT ~= -1 then
    game.dosafeverifysetdw1(dwID)
    if game.dosafeverify(4) ~= 1 then
      return 1
    end
    OnCreateDestroyItem(dwID)
  end
  return 1
end

function OnDestroyItem_Ok(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.parent(dwID)
  window.destroy(w)
  game.destroyitemslot(RES_DESTROY_SLOT)
  return 1
end

function OnDestroyItem_Cancel(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.parent(dwID)
  window.destroy(w)
  return 1
end

function OnOpenPackageInterface(dwID, dwCmdID, dwParam, pParam)
  CreatePackageWnd()
  return 1
end

function CreatePackageWnd()
  if window.isexist(WND_PACKAGE) then
    window.destroy(WND_PACKAGE)
    WND_PACKAGE = 0
    return 1
  end
  local PackageSize = game.getbagsize()
  local PackageNum
  if PackageSize == 0 then
    return 1
  elseif PackageSize <= 5 then
    PackageNum = 3401
  elseif PackageSize <= 10 then
    PackageNum = 3407
  elseif PackageSize <= 15 then
    PackageNum = 3418
  elseif PackageSize <= 20 then
    PackageNum = 3434
  elseif PackageSize <= 25 then
    PackageNum = 3455
  elseif PackageSize <= 30 then
    PackageNum = 3456
  elseif PackageSize <= 35 then
    PackageNum = 3457
  elseif PackageSize <= 40 then
    PackageNum = 3458
  elseif PackageSize <= 45 then
    PackageNum = 3459
  elseif PackageSize <= 50 then
    PackageNum = 3460
  else
    return 1
  end
  WND_PACKAGE = window.create(PackageNum, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_PACKAGE_X or 0 > WND_PACKAGE_Y then
    window.move(WND_PACKAGE, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_PACKAGE, WND_PACKAGE_X, WND_PACKAGE_Y)
  end
  game.inititemwnd(WND_PACKAGE, 1)
  window.regsetting(WND_PACKAGE, "WND_PACKAGE")
  return 1
end

function OnOpenEquipInterface(dwID, dwCmdID, dwParam, pParam)
  CreateEquipWnd()
  return 1
end

function CreateSaleInterface()
  WND_SALE = window.create(3081, 0, 0, SYSTEM_HANDLER)
  game.initsalewnd(WND_SALE)
  if 0 > WND_SALE_X or 0 > WND_SALE_Y then
    window.move(WND_SALE, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_SALE, WND_SALE_X, WND_SALE_Y)
  end
  window.regsetting(WND_SALE, "WND_SALE")
  SALEPAGE_SALE = window.find(WND_SALE, 3082)
  SALEPAGE_BUY = window.find(WND_SALE, 3089)
  window.show(SALEPAGE_SALE, true)
  window.show(SALEPAGE_BUY, false)
  if game.saleissale() then
    window.enable(window.find(WND_SALE, 3100), false)
    window.enable(window.find(WND_SALE, 3775), false)
    window.enable(window.find(WND_SALE, 3086), false)
    window.enable(window.find(WND_SALE, 3087), false)
  else
    window.enable(window.find(WND_SALE, 3088), false)
  end
  return 1
end

function OnOpenSaleInterface(dwID, dwCmdID, dwParam, pParam)
  if game.dosafeverify(1) ~= 1 then
    return 1
  end
  if window.isexist(WND_SALE) then
    return 1
  end
  CreateSaleInterface()
  return 1
end

function OnDragCharItem(dwID, dwCmdID, dwParam, pParam)
  game.dragcharitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropCharItem(dwID, dwCmdID, dwParam, pParam)
  game.dropcharitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnUseCharItem(dwID, dwCmdID, dwParam, pParam)
  local slot
  slot = game.getitemslot(dwCmdID)
  if 0 < slot then
    game.usecharitem(slot, true, dwID)
  end
  return 1
end

function CreateBindItemConfirmWnd(nResID, nFromSlot, nToSlot, bEquip, nStringID)
  local w, parent, text
  ITEM_CUR_SLOT = nFromSlot
  ITEM_TO_SLOT = nToSlot
  w = window.create(nResID, 0, 0, SYSTEM_HANDLER)
  if bEquip == false then
    text = window.find(w, 661)
    window.settitle(text, game.getstring(nStringID))
  end
  if 0 < window.width(WND_ITEM) then
    parent = WND_ITEM
    window.move(w, window.left(parent) + (window.width(parent) - window.width(w)) / 2, window.top(parent) + (window.height(parent) - window.height(w)) / 2)
  elseif 0 < window.width(WND_PACKAGE) then
    parent = WND_PACKAGE
    window.move(w, window.left(parent) + (window.width(parent) - window.width(w)) / 2, window.top(parent) + (window.height(parent) - window.height(w)) / 2)
  else
    window.move(w, (SYSTEM_SCREEN_WIDTH - window.width(w)) / 2, (SYSTEM_SCREEN_HEIGHT - window.height(w)) / 2)
  end
end

function OnUseCharBindItem_OK(dwID, dwCmdID, dwParam, pParam)
  game.usecharitem(ITEM_CUR_SLOT, false, dwID)
  window.destroy(window.parent(dwID))
  return 1
end

function OnUseCharBindItem_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnDropCharBindItem_OK(dwID, dwCmdID, dwParam, pParam)
  game.changeitemslot(ITEM_CUR_SLOT, ITEM_TO_SLOT)
  window.destroy(window.parent(dwID))
  return 1
end

WND_SPLIT_ITEM = 0

function CreateSplitItemWnd(dwWnd, nMax)
  local x, y, w
  WND_SPLIT_ITEM = window.create(3701, 0, 0, SYSTEM_HANDLER)
  x = window.left(dwWnd) - window.width(WND_SPLIT_ITEM) / 2
  y = window.top(dwWnd)
  window.move(WND_SPLIT_ITEM, x, y)
  w = window.find(WND_SPLIT_ITEM, 3704)
  window.setminnumber(w, 1)
  window.setmaxnumber(w, nMax)
  window.settitleint(w, 1)
  w = window.find(WND_SPLIT_ITEM, 3705)
  window.setrange(w, 1, nMax)
  window.setpos(w, 1)
end

function OnSplitItem(dwID, dwCmdID, dwParam, pParam)
  local w, num
  w = window.find(window.parent(dwID), 3704)
  num = window.gettitleint(w)
  if 0 < num then
    game.setsplititemnum(num)
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnEditChangeNumber(dwID, dwCmdID, dwParam, pParam)
  local w, num
  num = window.gettitleint(dwID)
  w = window.find(window.parent(dwID), 3705)
  window.setpos(w, num)
  return 1
end

function OnScrollNumber(dwID, dwCmdID, dwParam, pParam)
  local w, num
  num = window.getpos(dwID)
  w = window.find(window.parent(dwID), 3704)
  window.settitleint(w, num)
  return 1
end

function OnReinForceOK(dwID, dwCmdID, dwParam, pParam)
  game.useitem2itemconfirm(dwID)
  window.destroy(window.parent(dwID))
  WND_COMPOUNDBUFFWND = 0
  return 1
end

function OnSuperShoutOK(dwID, dwCmdID, dwParam, pParam)
  game.useitemsupershout(dwID)
  window.destroy(window.parent(dwID))
  return 1
end

WND_DOLLCARD_BAG = 0
WND_DOLLCARD_BAG_X = -1
WND_DOLLCARD_BAG_Y = -1
DOLLCARD_BAG_WND_RES_ID = 14770
DOLL_BAG_WND_RES_ID = 14780
CARD_BAG_WND_RES_ID = 14790
HOUSE_BAG_WND_RES_ID = 27019
DOLLCARD_BAG_RADIO_RES_ID_FIRST = 14771
DOLL_BAG_PAGE = 1
DOLL_BAG_PAGE_MAX = 4
CARD_BAG_PAGE = 1
CARD_BAG_PAGE_MAX = 2
HOUSE_BAG_PAGE = 1
HOUSE_BAG_PAGE_MAX = 4
SPEECH_BUBBLE_BAG_WND_RES_ID = 19007
SPEECH_BUBBLE_BAG_PAGE = 1
SPEECH_BUBBLE_BAG_PAGE_MAX = 2
BAG_BTN_PAGE = 1
BAG_BTN_PAGE_MAX = 2

function OnOpenDollCardBagInterface(dwID, dwCmdID, dwParam, pParam)
  CreateDollCardBagWnd()
  return 1
end

function CreateDollCardBagWnd()
  if game.isdef("__CARD") == false and game.isdef("__USA") == false then
    return 1
  end
  if game.isdef("__MALAYSIA") then
    DOLL_BAG_PAGE_MAX = 2
  end
  if window.isexist(WND_DOLLCARD_BAG) then
    window.destroy(WND_DOLLCARD_BAG)
    WND_DOLLCARD_BAG = 0
    return 1
  end
  WND_DOLLCARD_BAG = window.create(DOLLCARD_BAG_WND_RES_ID, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_DOLLCARD_BAG_X or 0 > WND_DOLLCARD_BAG_Y then
    window.move(WND_DOLLCARD_BAG, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_DOLLCARD_BAG, WND_DOLLCARD_BAG_X, WND_DOLLCARD_BAG_Y)
  end
  game.inititemwnd(WND_DOLLCARD_BAG, 4)
  window.regsetting(WND_DOLLCARD_BAG, "WND_DOLLCARD_BAG")
  local dwSelectedTag = window.find(WND_DOLLCARD_BAG, DOLLCARD_BAG_RADIO_RES_ID_FIRST)
  window.setcheck(dwSelectedTag, true)
  OnRadioDollCardBagChange(dwSelectedTag, 0, 0, 0)
  if not game.isdef("__CARD") then
    local dwCardBagTag = window.find(WND_DOLLCARD_BAG, 14772)
    window.show(dwCardBagTag, false)
  end
  if not game.isdef("__MY_HOUSE") then
    local dwCardBagTag = window.find(WND_DOLLCARD_BAG, 27018)
    window.show(dwCardBagTag, false)
  end
  DOLL_BAG_PAGE = 1
  UpdateDollBagPage(window.find(WND_DOLLCARD_BAG, DOLL_BAG_WND_RES_ID))
  CARD_BAG_PAGE = 1
  UpdateCardBagPage(window.find(WND_DOLLCARD_BAG, CARD_BAG_WND_RES_ID))
  HOUSE_BAG_PAGE = 1
  UpdateHouseBagPage(window.find(WND_DOLLCARD_BAG, HOUSE_BAG_WND_RES_ID))
  if game.isdef("__SPEECH_BUBBLE") == true then
    SPEECH_BUBBLE_BAG_PAGE = 1
    UpdateSpeechBubbleBagPage(window.find(WND_DOLLCARD_BAG, SPEECH_BUBBLE_BAG_WND_RES_ID))
    BAG_BTN_PAGE = 1
    UpdateBagBtnPage()
  end
  return 1
end

function OnRadioDollCardBagChange(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local nSelectedIndex = appdata - DOLLCARD_BAG_RADIO_RES_ID_FIRST + 1
  local tmpBagMax = 3
  local pWndResID = {
    DOLL_BAG_WND_RES_ID,
    CARD_BAG_WND_RES_ID,
    HOUSE_BAG_WND_RES_ID
  }
  if game.isdef("__SPEECH_BUBBLE") == true then
    tmpBagMax = 4
    pWndResID = {
      DOLL_BAG_WND_RES_ID,
      CARD_BAG_WND_RES_ID,
      HOUSE_BAG_WND_RES_ID,
      SPEECH_BUBBLE_BAG_WND_RES_ID
    }
  end
  for i = 1, tmpBagMax do
    if pWndResID[i] ~= 0 then
      if i == nSelectedIndex then
        window.show(window.find(window.parent(dwID), pWndResID[i]), true)
        window.settitle(window.parent(dwID), window.gettitle(dwID))
      else
        window.show(window.find(window.parent(dwID), pWndResID[i]), false)
      end
    end
  end
  return 1
end

function OnCloseDollCardBag(dwID, dwCmdID, dwParam, pParam)
  if WND_DOLLCARD_BAG ~= 0 and window.isexist(WND_DOLLCARD_BAG) then
    window.destroy(WND_DOLLCARD_BAG)
    WND_DOLLCARD_BAG = 0
    return 1
  end
end

function OnChangeBagBtnPage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  BAG_BTN_PAGE = BAG_BTN_PAGE + appdata
  if BAG_BTN_PAGE > BAG_BTN_PAGE_MAX then
    BAG_BTN_PAGE = BAG_BTN_PAGE_MAX
  elseif BAG_BTN_PAGE < 1 then
    BAG_BTN_PAGE = 1
  end
  UpdateBagBtnPage()
  return 1
end

function UpdateBagBtnPage()
  local tmpNowPage = BAG_BTN_PAGE
  local tmpResMax = 4
  local tmpWndResID = {
    14771,
    14772,
    27018,
    19006
  }
  local tmpStartIdx = 3 * (tmpNowPage - 1) + 1
  local tmpEndIdx = 3 * tmpNowPage
  for i = 1, tmpResMax do
    if i >= tmpStartIdx and i <= tmpEndIdx then
      window.show(window.find(WND_DOLLCARD_BAG, tmpWndResID[i]), true)
    else
      window.show(window.find(WND_DOLLCARD_BAG, tmpWndResID[i]), false)
    end
  end
  window.settitle(window.find(WND_DOLLCARD_BAG, 19013), tmpNowPage .. " / " .. BAG_BTN_PAGE_MAX)
  return 1
end

function OnDragSpeechBubbleBagItem(dwID, dwCmdID, dwParam, pParam)
  game.dragcharitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropSpeechBubbleBagItem(dwID, dwCmdID, dwParam, pParam)
  if game.dropcharitem(dwID, dwCmdID, dwParam, pParam) then
    return 1
  end
  return 0
end

function OnUseSpeechBubbleBagItem(dwID, dwCmdID, dwParam, pParam)
  local slot
  slot = game.getitemslot(dwCmdID)
  if 0 < slot then
    game.usecharitem(slot, false, dwID)
  end
  return 1
end

function OnChangeSpeechBubbleBagPage(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local appdata = window.getappdata(dwID)
  SPEECH_BUBBLE_BAG_PAGE = SPEECH_BUBBLE_BAG_PAGE + appdata
  if SPEECH_BUBBLE_BAG_PAGE > SPEECH_BUBBLE_BAG_PAGE_MAX then
    SPEECH_BUBBLE_BAG_PAGE = SPEECH_BUBBLE_BAG_PAGE_MAX
  elseif SPEECH_BUBBLE_BAG_PAGE < 1 then
    SPEECH_BUBBLE_BAG_PAGE = 1
  end
  UpdateSpeechBubbleBagPage(dwMainWndHD)
  return 1
end

function UpdateSpeechBubbleBagPage(dwMainWndHD)
  local pWndResID = {19011, 19012}
  for i = 1, SPEECH_BUBBLE_BAG_PAGE_MAX do
    if pWndResID[i] ~= 0 then
      if i == SPEECH_BUBBLE_BAG_PAGE then
        window.show(window.find(dwMainWndHD, pWndResID[i]), true)
      else
        window.show(window.find(dwMainWndHD, pWndResID[i]), false)
      end
    end
  end
  window.settitle(window.find(dwMainWndHD, 19008), SPEECH_BUBBLE_BAG_PAGE .. " / " .. SPEECH_BUBBLE_BAG_PAGE_MAX)
  return 1
end

function OnDragDollBagItem(dwID, dwCmdID, dwParam, pParam)
  game.dragcharitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropDollBagItem(dwID, dwCmdID, dwParam, pParam)
  if game.dropcharitem(dwID, dwCmdID, dwParam, pParam) then
    return 1
  end
  return 0
end

function OnUseDollBagItem(dwID, dwCmdID, dwParam, pParam)
  local slot
  slot = game.getitemslot(dwCmdID)
  if 0 < slot then
    game.usecharitem(slot, true, dwID)
  end
  return 1
end

function OnChangeDollBagPage(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local appdata = window.getappdata(dwID)
  DOLL_BAG_PAGE = DOLL_BAG_PAGE + appdata
  if DOLL_BAG_PAGE > DOLL_BAG_PAGE_MAX then
    DOLL_BAG_PAGE = DOLL_BAG_PAGE_MAX
  elseif DOLL_BAG_PAGE < 1 then
    DOLL_BAG_PAGE = 1
  end
  UpdateDollBagPage(dwMainWndHD)
  return 1
end

function UpdateDollBagPage(dwMainWndHD)
  local pWndResID = {
    14786,
    14787,
    14788,
    14789
  }
  for i = 1, DOLL_BAG_PAGE_MAX do
    if pWndResID[i] ~= 0 then
      if i == DOLL_BAG_PAGE then
        window.show(window.find(dwMainWndHD, pWndResID[i]), true)
      else
        window.show(window.find(dwMainWndHD, pWndResID[i]), false)
      end
    end
  end
  window.settitle(window.find(dwMainWndHD, 14781), DOLL_BAG_PAGE .. " / " .. DOLL_BAG_PAGE_MAX)
  return 1
end

function OnDragCardBagItem(dwID, dwCmdID, dwParam, pParam)
  game.dragcharitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropCardBagItem(dwID, dwCmdID, dwParam, pParam)
  if game.dropcharitem(dwID, dwCmdID, dwParam, pParam) then
    return 1
  end
  return 0
end

function OnUseCardBagItem(dwID, dwCmdID, dwParam, pParam)
  local slot
  slot = game.getitemslot(dwCmdID)
  if 0 < slot then
    game.usecharitem(slot, false, dwID)
  end
  return 1
end

function OnChangeCardBagPage(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local appdata = window.getappdata(dwID)
  CARD_BAG_PAGE = CARD_BAG_PAGE + appdata
  if CARD_BAG_PAGE > CARD_BAG_PAGE_MAX then
    CARD_BAG_PAGE = CARD_BAG_PAGE_MAX
  elseif CARD_BAG_PAGE < 1 then
    CARD_BAG_PAGE = 1
  end
  UpdateCardBagPage(dwMainWndHD)
  return 1
end

function UpdateCardBagPage(dwMainWndHD)
  local pWndResID = {
    14796,
    14797,
    14798,
    14799
  }
  for i = 1, CARD_BAG_PAGE_MAX do
    if pWndResID[i] ~= 0 then
      if i == CARD_BAG_PAGE then
        window.show(window.find(dwMainWndHD, pWndResID[i]), true)
      else
        window.show(window.find(dwMainWndHD, pWndResID[i]), false)
      end
    end
  end
  window.settitle(window.find(dwMainWndHD, 14791), CARD_BAG_PAGE .. " / " .. CARD_BAG_PAGE_MAX)
  return 1
end

function OnChangeHouseBagPage(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local appdata = window.getappdata(dwID)
  HOUSE_BAG_PAGE = HOUSE_BAG_PAGE + appdata
  if HOUSE_BAG_PAGE > HOUSE_BAG_PAGE_MAX then
    HOUSE_BAG_PAGE = HOUSE_BAG_PAGE_MAX
  elseif HOUSE_BAG_PAGE < 1 then
    HOUSE_BAG_PAGE = 1
  end
  UpdateHouseBagPage(dwMainWndHD)
  return 1
end

function UpdateHouseBagPage(dwMainWndHD)
  local pWndResID = {
    27024,
    27025,
    27026,
    27027
  }
  for i = 1, HOUSE_BAG_PAGE_MAX do
    if pWndResID[i] ~= 0 then
      if i == HOUSE_BAG_PAGE then
        window.show(window.find(dwMainWndHD, pWndResID[i]), true)
      else
        window.show(window.find(dwMainWndHD, pWndResID[i]), false)
      end
    end
  end
  window.settitle(window.find(dwMainWndHD, 27020), HOUSE_BAG_PAGE .. " / " .. HOUSE_BAG_PAGE_MAX)
  return 1
end

function OnUseExpPaper(dwID, dwCmdID, dwParam, pParam)
  local wnd
  local parent = window.parent(dwID)
  local appdata = window.getappdata(parent)
  local resMax, resIndex
  if game.isdef("__PEAK_LV_SYSTEM") == true then
    resMax = 8
    resIndex = 27690
  else
    resMax = 5
    resIndex = 27642
  end
  if appdata == 1 then
    game.useexppaper(window.getappdata(dwID), 0)
  elseif appdata == 3 then
    game.useexppaper(window.getappdata(dwID), 0)
  elseif appdata == 4 then
    game.useexppaper(window.getappdata(dwID), 0)
  elseif appdata == 2 then
    for i = 0, resMax do
      wnd = window.find(parent, resIndex + i)
      if window.ischeck(wnd) then
        game.useexppaper(window.getappdata(dwID), window.getappdata(wnd))
        window.destroy(window.parent(dwID))
        return 1
      end
    end
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnCloseExpPaperWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnUseItem(dwID, dwCmdID, dwParam, pParam)
  game.useitem(window.getappdata(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnUseSkillExpBall(dwID, dwCmdID, dwParam, pParam)
  local btn, idx, parent
  parent = window.parent(dwID)
  btn = window.find(parent, 28321)
  idx = window.getradio(btn)
  if 0 <= idx then
    btn = window.find(parent, 28321 + idx)
    game.useitem2target(window.getappdata(dwID), window.getappdata(btn))
    window.destroy(window.parent(dwID))
  end
  return 1
end
