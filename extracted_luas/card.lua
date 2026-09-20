WND_CARDBOOK = 0
WND_CARDSET = 0
WND_CARDLIST = 0
CARDBOOK_WINDOW_RES_ID = 14500
CARDBOOK_RADIO_RES_ID_FIRST = 14511
CARDSET_WINDOW_RES_ID = 14520
CARDLIST_WINDOW_RES_ID = 14600
CARDSET_REWARD_WINDOW_RES_ID = 14650
CARDHELP_WINDOW_RES_ID = 14690
CARDLIST_CARDUI_WINDOW_RES_ID = 14630

function OnClickOpenCardBook(dwID, dwCmdID, dwParam, pParam)
  CreateCardBookWindow()
  return 1
end

function CreateCardBookWindow()
  window.trace("CreateCardBookWindow")
  if window.isexist(WND_CARDBOOK) then
    if window.isvisible(WND_CARDBOOK) then
      window.show(WND_CARDBOOK, false)
    else
      window.show(WND_CARDBOOK, true)
      window.setforeground(WND_CARDBOOK)
    end
    return
  end
  WND_CARDBOOK = window.create(CARDBOOK_WINDOW_RES_ID, 0, 0, SYSTEM_HANDLER)
  WND_CARDSET = window.find(WND_CARDBOOK, CARDSET_WINDOW_RES_ID)
  WND_CARDLIST = window.find(WND_CARDBOOK, CARDLIST_WINDOW_RES_ID)
  window.regsetting(WND_CARDBOOK, "WND_CARDBOOK")
  local nSelectedPageWndHD = window.find(WND_CARDBOOK, CARDBOOK_RADIO_RES_ID_FIRST)
  window.setcheck(nSelectedPageWndHD, true)
  OnRadioCardBookChange(nSelectedPageWndHD, 0, 0, 0)
  CreateCardBook_CardSetWnd(WND_CARDSET)
  CreateCardBook_CardListWnd(WND_CARDLIST)
  return 1
end

function OnRadioCardBookChange(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local nSelectedIndex = appdata - CARDBOOK_RADIO_RES_ID_FIRST + 1
  local pWndResID = {
    CARDSET_WINDOW_RES_ID,
    CARDLIST_WINDOW_RES_ID,
    CARDHELP_WINDOW_RES_ID
  }
  for i = 1, 3 do
    if pWndResID[i] ~= 0 then
      if i == nSelectedIndex then
        window.show(window.find(window.parent(dwID), pWndResID[i]), true)
      else
        window.show(window.find(window.parent(dwID), pWndResID[i]), false)
      end
    end
  end
  return 1
end

CARDSET_TREE_HEADER_WND_RES_ID_FIRST = 14521
CARDSET_TREE_WINDOW_RES_ID = 14530
CARDSET_TREE_TIP_WINDOW_RES_ID = 14532
CARDSET_REWARD1_BTN_WND_RES_ID = 14653
CARDSET_REWARD2_BTN_WND_RES_ID = 14654
CARDSET_REWARD3_BTN_WND_RES_ID = 14655
CARDSET_REWARD1_ITEMPIC_WND_RES_ID = 14656
CARDSET_REWARD2_ITEMPIC_WND_RES_ID = 14657
CARDSET_REWARD3_ITEMPIC_WND_RES_ID = 14658

function CreateCardBook_CardSetWnd(WND_CARDSET)
  window.trace("Create CardBook:CardSetWindow")
  InitCardSetTree(WND_CARDSET)
  return 0
end

function InitCardSetTree(WND_CARDSET)
  local dwCardSetTreeHD = window.find(WND_CARDSET, CARDSET_TREE_WINDOW_RES_ID)
  local dwCardWndHD = window.find(WND_CARDSET, CARDLIST_CARDUI_WINDOW_RES_ID)
  local dwTipWndHD = window.find(WND_CARDSET, CARDSET_TREE_TIP_WINDOW_RES_ID)
  game.createcardsettree(dwCardSetTreeHD, dwCardWndHD, dwTipWndHD)
  return 1
end

function OnClickCardSetTreeItem(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardSetTreeHD = window.find(dwMainWndHD, CARDSET_TREE_WINDOW_RES_ID)
  local dwCardWndHD = window.find(dwMainWndHD, CARDLIST_CARDUI_WINDOW_RES_ID)
  local dwTipWndHD = window.find(dwMainWndHD, CARDSET_TREE_TIP_WINDOW_RES_ID)
  game.onclickcardsettreeitem(dwCardSetTreeHD, dwCardWndHD, dwTipWndHD)
  return 1
end

function OnRadioSortCardSetTree(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardSetTreeHD = window.find(dwMainWndHD, CARDSET_TREE_WINDOW_RES_ID)
  local appdata = window.getappdata(dwID)
  local nHeader = appdata - CARDSET_TREE_HEADER_WND_RES_ID_FIRST
  window.trace("cardset tree sort item ,header:" .. nHeader)
  game.cardsettreesortitem(dwCardSetTreeHD, nHeader)
  window.trace("cardset tree sort item ok")
  return 1
end

function OnTooltipCardSetReward(dwID, dwCmdID, dwParam, pParam)
  game.ontooltipatcardsetreward(dwID)
  return 1
end

function OnSelectCardSetReward(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnClickDoRewardCardSet(dwID, dwCmdID, dwParam, pParam)
  local dwRewardWndHD = window.parent(dwID)
  local dwRewardBtn1 = window.find(dwRewardWndHD, CARDSET_REWARD1_BTN_WND_RES_ID)
  local dwRewardBtn2 = window.find(dwRewardWndHD, CARDSET_REWARD2_BTN_WND_RES_ID)
  local dwRewardBtn3 = window.find(dwRewardWndHD, CARDSET_REWARD3_BTN_WND_RES_ID)
  if window.ischeck(dwRewardBtn1) then
    game.sentmsgtorewardcardset(dwRewardWndHD, 0)
  elseif window.ischeck(dwRewardBtn2) then
    game.sentmsgtorewardcardset(dwRewardWndHD, 1)
  elseif window.ischeck(dwRewardBtn3) then
    game.sentmsgtorewardcardset(dwRewardWndHD, 2)
  else
    game.sentmsgtorewardcardset(dwRewardWndHD, -1)
  end
  return 1
end

CARDLIST_LIST_WINDOW_RES_ID = 14620
CARDLIST_CLASSRADIO_WND_RES_ID_FIRST = 14601
CARDLIST_HEADER_WND_RES_ID_FIRST = 14606
CARDLIST_TIP_WINDOW_RES_ID = 14622

function CreateCardBook_CardListWnd(WND_CARDLIST)
  window.trace("Create CardBook:CardListWindow")
  InitClassRadio(WND_CARDLIST)
  InitCardList(WND_CARDLIST)
  window.trace("CardList create ok")
  return 0
end

function InitClassRadio(WND_CARDLIST)
  window.trace("Init Radio")
  local dwClassRadioBtnHD = {}
  local i
  for i = 1, 5 do
    dwClassRadioBtnHD[i] = window.find(WND_CARDLIST, CARDLIST_CLASSRADIO_WND_RES_ID_FIRST + i - 1)
    window.settitle(dwClassRadioBtnHD[i], game.getstring(1992 + i - 1))
  end
  window.setcheck(dwClassRadioBtnHD[1], true)
  return 1
end

function InitCardList(WND_CARDLIST)
  window.trace("Init Card List")
  local dwCardListHD = window.find(WND_CARDLIST, CARDLIST_LIST_WINDOW_RES_ID)
  local dwCardWndHD = window.find(WND_CARDLIST, CARDLIST_CARDUI_WINDOW_RES_ID)
  game.changecardlistdisplayclass(dwCardListHD, 0, dwCardWndHD)
  return 1
end

function OnClickCardListItem(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardListHD = window.find(dwMainWndHD, CARDLIST_LIST_WINDOW_RES_ID)
  local dwCardWndHD = window.find(dwMainWndHD, CARDLIST_CARDUI_WINDOW_RES_ID)
  local dwTipWndHD = window.find(dwMainWndHD, CARDLIST_TIP_WINDOW_RES_ID)
  game.onclickcardlistitem(dwCardListHD, dwCardWndHD, dwTipWndHD)
  return 1
end

function OnRadioCardListClass(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardListHD = window.find(dwMainWndHD, CARDLIST_LIST_WINDOW_RES_ID)
  local appdata = window.getappdata(dwID)
  local nCardClass = appdata - CARDLIST_CLASSRADIO_WND_RES_ID_FIRST
  local dwCardWndHD = window.find(dwMainWndHD, CARDLIST_CARDUI_WINDOW_RES_ID)
  game.changecardlistdisplayclass(dwCardListHD, nCardClass, dwCardWndHD)
  return 1
end

function OnRadioSortCardList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardListHD = window.find(dwMainWndHD, CARDLIST_LIST_WINDOW_RES_ID)
  local appdata = window.getappdata(dwID)
  local nHeader = appdata - CARDLIST_HEADER_WND_RES_ID_FIRST
  window.trace("cardlist sort item ,header:" .. nHeader)
  game.cardlistsortitem(dwCardListHD, nHeader)
  window.trace("cardlist sort item ok")
  return 1
end

WND_SIMPLFY_CARDBOOK = 0
WND_SIMPLFY_CARDSET = 0
WND_SIMPLFY_CARDLIST = 0
SIMPLFY_CARDBOOK_WINDOW_RES_ID = 14700
SIMPLFY_CARDBOOK_RADIO_RES_ID_FIRST = 14701
SIMPLFY_CARDSET_WINDOW_RES_ID = 14710
SIMPLFY_CARDLIST_WINDOW_RES_ID = 14730

function CreateSimplfyCardBookWindow()
  window.trace("CreateSimplfyCardBookWindow")
  if window.isexist(WND_SIMPLFY_CARDBOOK) then
    window.destroy(WND_SIMPLFY_CARDBOOK)
    WND_SIMPLFY_CARDBOOK = 0
  end
  WND_SIMPLFY_CARDBOOK = window.create(SIMPLFY_CARDBOOK_WINDOW_RES_ID, 0, 0, SYSTEM_HANDLER)
  WND_SIMPLFY_CARDSET = window.find(WND_SIMPLFY_CARDBOOK, SIMPLFY_CARDSET_WINDOW_RES_ID)
  WND_SIMPLFY_CARDLIST = window.find(WND_SIMPLFY_CARDBOOK, SIMPLFY_CARDLIST_WINDOW_RES_ID)
  window.regsetting(WND_SIMPLFY_CARDBOOK, "WND_SIMPLFY_CARDBOOK")
  game.setotherplayercardbooktitle(WND_SIMPLFY_CARDBOOK)
  local nSelectedPageWndHD = window.find(WND_SIMPLFY_CARDBOOK, SIMPLFY_CARDBOOK_RADIO_RES_ID_FIRST + 1)
  window.setcheck(nSelectedPageWndHD, true)
  OnRadioSimplfyCardBookChange(nSelectedPageWndHD, 0, 0, 0)
  CreateSimplfyCardBook_CardSetWnd(WND_SIMPLFY_CARDSET)
  CreateSimplfyCardBook_CardListWnd(WND_SIMPLFY_CARDLIST)
  return 1
end

function OnRadioSimplfyCardBookChange(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local nSelectedIndex = appdata - SIMPLFY_CARDBOOK_RADIO_RES_ID_FIRST + 1
  local pWndResID = {SIMPLFY_CARDSET_WINDOW_RES_ID, SIMPLFY_CARDLIST_WINDOW_RES_ID}
  for i = 1, 2 do
    if pWndResID[i] ~= 0 then
      if i == nSelectedIndex then
        window.show(window.find(window.parent(dwID), pWndResID[i]), true)
      else
        window.show(window.find(window.parent(dwID), pWndResID[i]), false)
      end
    end
  end
  return 1
end

SIMPLFY_CARDSET_TREE_HEADER_WND_RES_ID_FIRST = 14711
SIMPLFY_CARDSET_TREE_WINDOW_RES_ID = 14720

function CreateSimplfyCardBook_CardSetWnd(WND_SIMPLFY_CARDSET)
  window.trace("Create Simply CardBook:CardSetWindow")
  InitSimplfyCardSetTree(WND_SIMPLFY_CARDSET)
  InitSimplfyCardSetCardWnd(WND_SIMPLFY_CARDSET)
  window.trace("Simply CardSet create ok")
  return 0
end

function InitSimplfyCardSetTree(WND_SIMPLFY_CARDSET)
  local dwCardSetTreeHD = window.find(WND_SIMPLFY_CARDSET, SIMPLFY_CARDSET_TREE_WINDOW_RES_ID)
  local dwCardWndHD = window.find(WND_SIMPLFY_CARDSET, CARDLIST_CARDUI_WINDOW_RES_ID)
  game.createsimplfycardsettree(dwCardSetTreeHD, dwCardWndHD)
  game.onclicksimplfycardsettreeitem(dwCardSetTreeHD, dwCardWndHD)
  return 1
end

function InitSimplfyCardSetCardWnd(WND_SIMPLFY_CARDSET)
  local dwCardWndHD = window.find(WND_SIMPLFY_CARDSET, CARDLIST_CARDUI_WINDOW_RES_ID)
  window.move(dwCardWndHD, window.left(WND_SIMPLFY_CARDSET) + 288, window.top(WND_SIMPLFY_CARDSET) + 27)
end

function OnClickSimplfyCardSetTreeItem(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardSetTreeHD = window.find(dwMainWndHD, SIMPLFY_CARDSET_TREE_WINDOW_RES_ID)
  local dwCardWndHD = window.find(dwMainWndHD, CARDLIST_CARDUI_WINDOW_RES_ID)
  game.onclicksimplfycardsettreeitem(dwCardSetTreeHD, dwCardWndHD)
  return 1
end

function OnRadioSortSimplfyCardSetTree(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardSetTreeHD = window.find(dwMainWndHD, SIMPLFY_CARDSET_TREE_WINDOW_RES_ID)
  local appdata = window.getappdata(dwID)
  local nHeader = appdata - SIMPLFY_CARDSET_TREE_HEADER_WND_RES_ID_FIRST
  window.trace("cardset tree sort item ,header:" .. nHeader)
  game.cardsettreesortitem(dwCardSetTreeHD, nHeader)
  window.trace("cardset tree sort item ok")
  return 1
end

SIMPLFY_CARDLIST_HEADER_WND_RES_ID_FIRST = 14731
SIMPLFY_CARDLIST_LIST_WINDOW_RES_ID = 14740

function CreateSimplfyCardBook_CardListWnd(WND_SIMPLFY_CARDLIST)
  window.trace("Create Simply CardBook:CardListWindow")
  InitSimplfyCardList(WND_SIMPLFY_CARDLIST)
  InitSimplfyCardListCardWnd(WND_SIMPLFY_CARDLIST)
  window.trace("Simply CardList create ok")
  return 0
end

function InitSimplfyCardList(WND_SIMPLFY_CARDLIST)
  window.trace("Init Simplfy Card List")
  local dwCardListHD = window.find(WND_SIMPLFY_CARDLIST, SIMPLFY_CARDLIST_LIST_WINDOW_RES_ID)
  local dwCardWndHD = window.find(WND_SIMPLFY_CARDLIST, CARDLIST_CARDUI_WINDOW_RES_ID)
  game.createsimplfycardlist(dwCardListHD, dwCardWndHD)
  game.onclicksimplfycardlistitem(dwCardListHD, dwCardWndHD)
  return 1
end

function InitSimplfyCardListCardWnd(WND_SIMPLFY_CARDLIST)
  local dwCardWndHD = window.find(WND_SIMPLFY_CARDLIST, CARDLIST_CARDUI_WINDOW_RES_ID)
  window.move(dwCardWndHD, window.left(WND_SIMPLFY_CARDLIST) + 288, window.top(WND_SIMPLFY_CARDLIST) + 27)
end

function OnClickSimplfyCardListItem(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardListHD = window.find(dwMainWndHD, SIMPLFY_CARDLIST_LIST_WINDOW_RES_ID)
  local dwCardWndHD = window.find(dwMainWndHD, CARDLIST_CARDUI_WINDOW_RES_ID)
  game.onclicksimplfycardlistitem(dwCardListHD, dwCardWndHD)
  return 1
end

function OnRadioSimplfySortCardList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwCardListHD = window.find(dwMainWndHD, SIMPLFY_CARDLIST_LIST_WINDOW_RES_ID)
  local appdata = window.getappdata(dwID)
  local nHeader = appdata - SIMPLFY_CARDLIST_HEADER_WND_RES_ID_FIRST + 1
  window.trace("cardlist sort item ,header:" .. nHeader)
  game.cardlistsortitem(dwCardListHD, nHeader)
  window.trace("cardlist sort item ok")
  return 1
end

WND_USECARD_VERIFY = 0
USECARD_SLOT = 0

function CreateUseCardVerifyWindow(nSlot)
  window.trace("CreateUseCardVerifyWindow")
  if WND_ITEM == 0 then
    return
  end
  WND_USECARD_VERIFY = window.create(14490, WND_ITEM, 0, 0)
  local nX = window.left(WND_ITEM) + (window.width(WND_ITEM) - window.width(WND_USECARD_VERIFY)) / 2
  local nY = window.top(WND_ITEM) + (window.height(WND_ITEM) - window.height(WND_USECARD_VERIFY)) / 2
  window.move(WND_USECARD_VERIFY, nX, nY)
  USECARD_SLOT = nSlot
  window.trace("CreateUseCardVerifyWindow4")
  return
end

function OnUseCardItem_OK(dwID, dwCmdID, dwParam, pParam)
  game.usecardaddtocardbook(USECARD_SLOT)
  local w = window.parent(dwID)
  window.destroy(w)
  return 1
end

function OnUseCardItem_Cancel(dwID, dwCmdID, dwParam, pParam)
  local w = window.parent(dwID)
  window.destroy(w)
  return 1
end
