WND_SALEWORDS = 0
WND_NPCSALE = 0
WND_PLAYERSALE = 0
WND_SALE_TRADE = 0
WND_NPCSALE_X = -1
WND_NPCSALE_Y = -1
WND_SALE_TRADE_X = -1
WND_SALE_TRADE_Y = -1
NPCSALE_LEARN_SCROLL_ONLY = 0

function OnNPCSaleClose(dwID, dwCmdID, dwParam, pParam)
  local w
  window.destroy(WND_NPCSALE)
  WND_NPCSALE = 0
  game.playnpcvoice(voiceThank)
  return 1
end

function OnSale_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnSaleListSave(dwID, dwCmdID, dwParam, pParam)
  game.salelistsave()
  return 1
end

function OnSale_ChaPage_Sale(dwID, dwCmdID, dwParam, pParam)
  local Sale = window.parent(dwID)
  local SalePage = window.find(Sale, 3082)
  local BuyPage = window.find(Sale, 3089)
  window.show(SalePage, true)
  window.show(window.find(Sale, 3100), true)
  window.show(BuyPage, false)
  window.show(window.find(Sale, 3775), false)
  local Btn_SalePage = window.find(Sale, 3084)
  local Btn_BuyPage = window.find(Sale, 3085)
  window.seticon(Btn_SalePage, 3085)
  window.seticon(Btn_BuyPage, 3084)
  return 1
end

function OnSale_ChaPage_Buy(dwID, dwCmdID, dwParam, pParam)
  local Sale = window.parent(dwID)
  local SalePage = window.find(Sale, 3082)
  local BuyPage = window.find(Sale, 3089)
  window.show(SalePage, false)
  window.show(window.find(Sale, 3100), false)
  window.show(BuyPage, true)
  window.show(window.find(Sale, 3775), true)
  local Btn_SalePage = window.find(Sale, 3084)
  local Btn_BuyPage = window.find(Sale, 3085)
  window.seticon(Btn_SalePage, 3084)
  window.seticon(Btn_BuyPage, 3085)
  return 1
end

function OnDelSaleItem(dwID, dwCmdID, dwParam, pParam)
  game.deletesalelist(window.parent(dwID))
  return 1
end

function OnDelSaleItemEx(dwID, dwCmdID, dwParam, pParam)
  game.deletesalelistex(window.parent(dwID))
  return 1
end

function OnOpenSaleWords(dwID, dwCmdID, dwParam, pParam)
  game.showsalemessage(window.parent(dwID))
  return 1
end

function OnSaleWords_Ok(dwID, dwCmdID, dwParam, pParam)
  game.salemessage(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnStartSale(dwID, dwCmdID, dwParam, pParam)
  game.salestart(window.parent(dwID))
  return 1
end

function OnStartSale_OK(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.salestartok()
  return 1
end

function OnStartSale_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnCloseSale(dwID, dwCmdID, dwParam, pParam)
  game.saleclose(window.parent(dwID))
  return 1
end

function OnCloseSale_OK(dwID, dwCmdID, dwParam, pParam)
  game.salecloseok()
  window.destroy(window.parent(dwID))
  return 1
end

function OnCloseSale_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnNPCSale_ChaPage_Buy(dwID, dwCmdID, dwParam, pParam)
  local WndNPCSale = window.parent(dwID)
  local BuyPage = window.find(WndNPCSale, 3604)
  local SalePage = window.find(WndNPCSale, 3605)
  window.show(BuyPage, true)
  window.show(SalePage, false)
  local Btn_BuyPage = window.find(WndNPCSale, 3602)
  local Btn_SalePage = window.find(WndNPCSale, 3603)
  window.seticon(Btn_BuyPage, 3085)
  window.seticon(Btn_SalePage, 3084)
  return 1
end

function OnNPCSale_ChaPage_Buy2(dwID, dwCmdID, dwParam, pParam)
  local WndNPCSale = window.parent(dwID)
  local BuyPage = window.find(WndNPCSale, 13404)
  local SalePage = window.find(WndNPCSale, 13405)
  window.show(BuyPage, true)
  window.show(SalePage, false)
  local Btn_BuyPage = window.find(WndNPCSale, 13402)
  local Btn_SalePage = window.find(WndNPCSale, 13403)
  window.seticon(Btn_BuyPage, 3085)
  window.seticon(Btn_SalePage, 3084)
  return 1
end

function OnNPCSale_ChaPage_Sale(dwID, dwCmdID, dwParam, pParam)
  local WndNPCSale = window.parent(dwID)
  local BuyPage = window.find(WndNPCSale, 3604)
  local SalePage = window.find(WndNPCSale, 3605)
  window.show(BuyPage, false)
  window.show(SalePage, true)
  local Btn_BuyPage = window.find(WndNPCSale, 3602)
  local Btn_SalePage = window.find(WndNPCSale, 3603)
  window.seticon(Btn_BuyPage, 3084)
  window.seticon(Btn_SalePage, 3085)
  return 1
end

function OnNPCSale_ChaPage_Sale2(dwID, dwCmdID, dwParam, pParam)
  local WndNPCSale = window.parent(dwID)
  local BuyPage = window.find(WndNPCSale, 13404)
  local SalePage = window.find(WndNPCSale, 13405)
  window.show(BuyPage, false)
  window.show(SalePage, true)
  local Btn_BuyPage = window.find(WndNPCSale, 13402)
  local Btn_SalePage = window.find(WndNPCSale, 13403)
  window.seticon(Btn_BuyPage, 3084)
  window.seticon(Btn_SalePage, 3085)
  return 1
end

function OnPlayerSale_ChaPage_Buy(dwID, dwCmdID, dwParam, pParam)
  local WndPlayerSale = window.parent(dwID)
  local BuyPage = window.find(WndPlayerSale, 3654)
  local SalePage = window.find(WndPlayerSale, 3655)
  window.show(BuyPage, true)
  window.show(window.find(WndPlayerSale, 3668), true)
  window.show(SalePage, false)
  window.show(window.find(WndPlayerSale, 3679), false)
  local Btn_BuyPage = window.find(WndPlayerSale, 3652)
  local Btn_SalePage = window.find(WndPlayerSale, 3653)
  window.seticon(Btn_BuyPage, 3085)
  window.seticon(Btn_SalePage, 3084)
  WND_PLAYERSALE = 0
  game.setsalenum()
  return 1
end

function OnPlayerSale_ChaPage_Buy2(dwID, dwCmdID, dwParam, pParam)
  local WndPlayerSale = window.parent(dwID)
  local BuyPage = window.find(WndPlayerSale, 13554)
  local SalePage = window.find(WndPlayerSale, 13555)
  window.show(BuyPage, true)
  window.show(window.find(WndPlayerSale, 13568), true)
  window.show(SalePage, false)
  window.show(window.find(WndPlayerSale, 13579), false)
  local Btn_BuyPage = window.find(WndPlayerSale, 13552)
  local Btn_SalePage = window.find(WndPlayerSale, 13553)
  window.seticon(Btn_BuyPage, 3085)
  window.seticon(Btn_SalePage, 3084)
  WND_PLAYERSALE = 0
  game.setsalenum()
  return 1
end

function OnCheckLearnScrollOnly(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    NPCSALE_LEARN_SCROLL_ONLY = 1
  else
    NPCSALE_LEARN_SCROLL_ONLY = 0
  end
  game.updatenpcsaleitemwnd()
  return 1
end

function OnPlayerSale_ChaPage_Sale(dwID, dwCmdID, dwParam, pParam)
  local WndPlayerSale = window.parent(dwID)
  local BuyPage = window.find(WndPlayerSale, 3654)
  local SalePage = window.find(WndPlayerSale, 3655)
  window.show(BuyPage, false)
  window.show(window.find(WndPlayerSale, 3668), false)
  window.show(SalePage, true)
  window.show(window.find(WndPlayerSale, 3679), true)
  local Btn_BuyPage = window.find(WndPlayerSale, 3652)
  local Btn_SalePage = window.find(WndPlayerSale, 3653)
  window.seticon(Btn_BuyPage, 3084)
  window.seticon(Btn_SalePage, 3085)
  WND_PLAYERSALE = 1
  game.setsalenum()
  return 1
end

function OnPlayerSale_ChaPage_Sale2(dwID, dwCmdID, dwParam, pParam)
  local WndPlayerSale = window.parent(dwID)
  local BuyPage = window.find(WndPlayerSale, 13554)
  local SalePage = window.find(WndPlayerSale, 13555)
  window.show(BuyPage, false)
  window.show(window.find(WndPlayerSale, 13568), false)
  window.show(SalePage, true)
  window.show(window.find(WndPlayerSale, 13579), true)
  local Btn_BuyPage = window.find(WndPlayerSale, 13552)
  local Btn_SalePage = window.find(WndPlayerSale, 13553)
  window.seticon(Btn_BuyPage, 3084)
  window.seticon(Btn_SalePage, 3085)
  WND_PLAYERSALE = 1
  game.setsalenum()
  return 1
end

function OnDropSellSaleList(dwID, dwCmdID, dwParam, pParam)
  game.dropsellsalelist(pParam)
  return 1
end

function OnDropBuySaleList(dwID, dwCmdID, dwParam, pParam)
  game.dropbuysalelist(pParam)
  return 1
end

function OnSale_Scroll(dwID, dwCmdID, dwParam, pParam)
  game.salescroll(dwID, dwParam)
  return 1
end

function OnSaleSell_Single_OK(dwID, dwCmdID, dwParam, pParam)
  game.salesellsingle(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnSaleSell_Multiple_OK(dwID, dwCmdID, dwParam, pParam)
  game.salesellmultiple(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnSaleBuy_Single_OK(dwID, dwCmdID, dwParam, pParam)
  game.salebuysingle(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnSaleBuy_Multiple_OK(dwID, dwCmdID, dwParam, pParam)
  game.salebuymultiple(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnSaleEditChange(dwID, dwCmdID, dwParam, pParam)
  game.saleeditchange(dwID)
  return 1
end

function OnSaleTrade(dwID, dwCmdID, dwParam, pParam)
  if game.saleistrade() then
    game.addsystemmessage(339)
    return 1
  elseif game.saleissale() or window.isexist(WND_SALE_TRADE) then
    return 1
  end
  WND_SALE_TRADE = window.create(13551, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_SALE_TRADE_X or 0 > WND_SALE_TRADE_Y then
    window.move(WND_SALE_TRADE, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_SALE_TRADE, WND_SALE_TRADE_X, WND_SALE_TRADE_Y)
  end
  window.regsetting(WND_SALE_TRADE, "WND_SALE_TRADE")
  window.enable(window.find(WND_SALE_TRADE, 13568), false)
  game.saletradewnd(dwID)
  return 1
end

function OnSaleNum(dwID, dwCmdID, dwParam, pParam)
  game.dosaleautoadd()
  game.setsalenum()
  return 1
end

function OnSale_TradeScroll(dwID, dwCmdID, dwParam, pParam)
  game.saletradescroll(dwID, dwParam)
  return 1
end

function OnSaleTradeEditChange(dwID, dwCmdID, dwParam, pParam)
  game.saletradeeditchange(dwID)
  return 1
end

function OnSaleTradeBuy(dwID, dwCmdID, dwParam, pParam)
  game.saletradebuy()
  return 1
end

function OnSaleTradeBuyConfirm(dwID, dwCmdID, dwParam, pParam)
  game.saletradebuyconfirm(window.parent(dwID))
  return 1
end

function OnSaleTradeSell(dwID, dwCmdID, dwParam, pParam)
  game.saletradesell()
  return 1
end

function OnSaleTradeSellConfirm(dwID, dwCmdID, dwParam, pParam)
  game.saletradesellconfirm(window.parent(dwID))
  return 1
end

function OnSaleCloseTrade(dwID, dwCmdID, dwParam, pParam)
  game.salesettrade(false)
  window.destroy(WND_SALE_TRADE)
  WND_SALE_TRADE = 0
  return 1
end

function OnNPCSaleBuyEdit(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, -1)
  game.setbuyvalue(window.parent(dwID), false)
  return 1
end

function OnNPCSaleBuyScroll(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, dwParam)
  game.setbuyvalue(window.parent(dwID), false)
  return 1
end

function OnNPCSaleSellEdit(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, -1)
  game.setsellvalue(window.parent(dwID), false)
  return 1
end

function OnNPCSaleSellScroll(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, dwParam)
  game.setsellvalue(window.parent(dwID), false)
  return 1
end

function OnNPCSaleBuy(dwID, dwCmdID, dwParam, pParam)
  game.npcsalebuy(window.parent(dwID))
  return 1
end

function OnNPCSaleBuyConfirm(dwID, dwCmdID, dwParam, pParam)
  game.npcsalebuyconfirm(window.parent(dwID))
  return 1
end

function OnNPCSaleSell(dwID, dwCmdID, dwParam, pParam)
  game.npcsalesell(window.parent(dwID))
  return 1
end

function OnNPCSaleSellConfirm(dwID, dwCmdID, dwParam, pParam)
  game.npcsalesellconfirm(window.parent(dwID))
  return 1
end

function OnNPCSaleBuyEx(dwID, dwCmdID, dwParam, pParam)
  game.npcsalebuyex(window.parent(dwID), dwParam)
  return 1
end

function OnNPCSaleSellEx(dwID, dwCmdID, dwParam, pParam)
  game.npcsalesellex(window.parent(dwID), dwParam)
  return 1
end

function OnSetBuyValue(dwID, dwCmdID, dwParam, pParam)
  game.setbuyvalue(window.parent(dwID), true)
  return 1
end

function OnSetSellValue(dwID, dwCmdID, dwParam, pParam)
  game.setsellvalue(window.parent(dwID), true)
  return 1
end

function OnSaleUse_OK(dwID, dwCmdID, dwParam, pParam)
  game.useextrasaleslot(dwID)
  window.destroy(window.parent(dwID))
  return 1
end

function OnSaleUse_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end
