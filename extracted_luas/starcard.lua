WND_STARCARD_MAIN = 0
NOW_STARCARD_PAGE = 0
SAVE_STARCARD_APPDATA = 0
EXCHANGE_STARCARD_APPDATA = 0
WND_STARCARD_CONFIRM_EXCHANGE = 0
WND_STARCARD_CONFIRM_BINGO = 0
WND_STARCARD_CONFIRM_COIN = 0
WND_STARCARD_EXCHANGE = 0
NOW_EXCHANGE_PAGE = 1
NOW_EXCHANGE_SUB_PAGE = 1

function CloseStarCardWnd()
  if window.isexist(WND_STARCARD_MAIN) then
    WND_STARCARD_CONFIRM_EXCHANGE = 0
    WND_STARCARD_CONFIRM_BINGO = 0
    window.destroy(WND_STARCARD_MAIN)
    WND_STARCARD_MAIN = 0
  end
  return 1
end

function CreateStarCardWnd()
  if window.isexist(WND_STARCARD_MAIN) == true then
    CloseStarCardWnd()
  else
    NOW_STARCARD_PAGE = 0
    SAVE_STARCARD_APPDATA = 0
    EXCHANGE_STARCARD_APPDATA = 0
    WND_STARCARD_CONFIRM_EXCHANGE = 0
    WND_STARCARD_CONFIRM_BINGO = 0
    WND_STARCARD_CONFIRM_COIN = 0
    WND_STARCARD_EXCHANGE = 0
    NOW_EXCHANGE_PAGE = 1
    NOW_EXCHANGE_SUB_PAGE = 1
    window.regsetting(WND_STARCARD_MAIN, "WND_STARCARD_MAIN")
    WND_STARCARD_MAIN = window.create(50010, 0, 0, SYSTEM_HANDLER)
    window.move(WND_STARCARD_MAIN, 100, 100)
    UpdateStarCardUI()
    OpenMainStarCard()
    game.setcommandnotify(5, 0)
  end
  return 1
end

function StarCardNormalGet(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  window.trace("appdata" .. appdata)
  game.netcommand(70, appdata)
  return 1
end

function StarCardGoldenGet(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(70, 101)
  window.destroy(window.parent(dwID))
  WND_STARCARD_CONFIRM_COIN = 0
  return 1
end

function CoinCheck(dwID, dwCmdID, dwParam, pParam)
  game.showBestCoin(window.parent(dwID))
  return 1
end

function CreateStarCardCoinConfirm()
  if WND_STARCARD_CONFIRM_COIN == 0 then
    WND_STARCARD_CONFIRM_COIN = window.create(50390, WND_STARCARD_MAIN, 0, 0)
    game.showConfirmCoin(WND_STARCARD_MAIN)
    window.move(WND_STARCARD_CONFIRM_COIN, 382, 280)
  end
  return 1
end

function StarCardCancelCoin(dwID, dwCmdID, dwParam, pParam)
  WND_STARCARD_CONFIRM_COIN = 0
  window.destroy(window.parent(dwID))
  return 1
end

function TurnAllToPower()
  game.netcommand(70, 15)
  return 1
end

function AutoGetCard()
  game.netcommand(70, 13)
  return 1
end

function ResetBingo()
  game.netcommand(70, 18)
  return 1
end

function GetBingoReward()
  game.netcommand(70, 16)
  return 1
end

function GetABingo(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(70, 17)
  window.destroy(window.parent(dwID))
  WND_STARCARD_CONFIRM_BINGO = 0
  return 1
end

function BingoCheck(dwID, dwCmdID, dwParam, pParam)
  game.showBingoCoin(window.parent(dwID))
  return 1
end

function CreateStarCardBingoConfirm()
  if WND_STARCARD_CONFIRM_BINGO == 0 then
    WND_STARCARD_CONFIRM_BINGO = window.create(50380, WND_STARCARD_MAIN, 0, 0)
    game.showConfirmBingo(WND_STARCARD_MAIN)
    window.move(WND_STARCARD_CONFIRM_BINGO, 382, 280)
  end
  return 1
end

function StarCardCancelBingo(dwID, dwCmdID, dwParam, pParam)
  WND_STARCARD_CONFIRM_BINGO = 0
  window.destroy(window.parent(dwID))
  return 1
end

function StarcardLevelUp()
  game.netcommand(70, 12)
  window.trace("\164\201\175\197")
  return 1
end

function ShowStarPower()
  local s2 = game.getStarPower()
  local wnd = window.find(WND_STARCARD_MAIN, 50051)
  local wnd2 = window.find(WND_STARCARD_MAIN, 50050)
  window.settitle(wnd, s2)
  window.settitle(wnd2, s2)
end

function UpdateStarCardUI()
  if WND_STARCARD_MAIN ~= 0 then
    ShowStarPower()
    game.showTempSlot(WND_STARCARD_MAIN)
    game.showMainStarCard(WND_STARCARD_MAIN)
    if NOW_STARCARD_PAGE == 3 then
      game.changeSCExchangeSubPage(WND_STARCARD_EXCHANGE, NOW_EXCHANGE_PAGE, NOW_EXCHANGE_SUB_PAGE, 0)
    end
  end
  return 1
end

function OpenMainStarCard()
  local wnd = window.find(WND_STARCARD_MAIN, 50012)
  window.show(wnd, true)
  wnd = window.find(WND_STARCARD_MAIN, 50013)
  window.show(wnd, true)
  wnd = window.find(WND_STARCARD_MAIN, 50014)
  window.show(wnd, true)
  wnd = window.find(WND_STARCARD_MAIN, 50016)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50017)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50230)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50018)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50002)
  window.setradio(wnd, 0)
  NOW_STARCARD_PAGE = 1
  UpdateStarCardUI()
  return 1
end

function OpenLottery()
  local wnd = window.find(WND_STARCARD_MAIN, 50012)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50014)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50013)
  window.show(wnd, true)
  wnd = window.find(WND_STARCARD_MAIN, 50016)
  window.show(wnd, true)
  wnd = window.find(WND_STARCARD_MAIN, 50017)
  window.show(wnd, true)
  wnd = window.find(WND_STARCARD_MAIN, 50230)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50018)
  window.show(wnd, false)
  NOW_STARCARD_PAGE = 2
  UpdateStarCardUI()
  return 1
end

function OpenExchange(dwID, dwCmdID, dwParam, pParam)
  local wnd = window.find(WND_STARCARD_MAIN, 50012)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50013)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50014)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50016)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50017)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50018)
  window.show(wnd, false)
  WND_STARCARD_EXCHANGE = window.find(WND_STARCARD_MAIN, 50230)
  window.show(WND_STARCARD_EXCHANGE, true)
  NOW_STARCARD_PAGE = 3
  StarCardExchangePerfect()
  return 1
end

function OpenStarExplain(dwID, dwCmdID, dwParam, pParam)
  local wnd = window.find(WND_STARCARD_MAIN, 50012)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50013)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50014)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50016)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50017)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50230)
  window.show(wnd, false)
  wnd = window.find(WND_STARCARD_MAIN, 50018)
  window.show(wnd, true)
  local word = window.find(WND_STARCARD_MAIN, 50082)
  window.settitle(word, game.getstring(3643) .. game.getstring(3648))
  NOW_STARCARD_PAGE = 4
  return 1
end

function StarCardExchangePerfect()
  NOW_EXCHANGE_PAGE = 1
  game.showExchange(WND_STARCARD_EXCHANGE, NOW_EXCHANGE_PAGE)
  NOW_EXCHANGE_SUB_PAGE = 1
  return 1
end

function StarCardExchangeGod()
  NOW_EXCHANGE_PAGE = 2
  game.showExchange(WND_STARCARD_EXCHANGE, NOW_EXCHANGE_PAGE)
  NOW_EXCHANGE_SUB_PAGE = 1
  return 1
end

function StarCardExchangeSubChange(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  NOW_EXCHANGE_SUB_PAGE = game.changeSCExchangeSubPage(WND_STARCARD_EXCHANGE, NOW_EXCHANGE_PAGE, NOW_EXCHANGE_SUB_PAGE, appdata)
  return 1
end

function StarCardPushExchangeBtn(dwID, dwCmdID, dwParam, pParam)
  if WND_STARCARD_CONFIRM_EXCHANGE == 0 then
    EXCHANGE_STARCARD_APPDATA = (NOW_EXCHANGE_SUB_PAGE - 1) * 10 + window.getappdata(dwID)
    game.sendExchange(NOW_EXCHANGE_PAGE, EXCHANGE_STARCARD_APPDATA)
    window.trace("appdata is" .. EXCHANGE_STARCARD_APPDATA)
  end
  return 1
end

function CreateStarCardExchangeInfo()
  if WND_STARCARD_CONFIRM_EXCHANGE == 0 then
    WND_STARCARD_CONFIRM_EXCHANGE = window.create(50066, WND_STARCARD_MAIN, 0, 0)
    game.showConfirmExchange(WND_STARCARD_MAIN)
    window.move(WND_STARCARD_CONFIRM_EXCHANGE, 382, 252)
  end
  return 1
end

function StarCardConfirmExchange(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(70, 20)
  EXCHANGE_STARCARD_APPDATA = 0
  WND_STARCARD_CONFIRM_EXCHANGE = 0
  window.destroy(window.parent(dwID))
  return 1
end

function StarCardCancelExchange(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(70, 21)
  EXCHANGE_STARCARD_APPDATA = 0
  WND_STARCARD_CONFIRM_EXCHANGE = 0
  window.destroy(window.parent(dwID))
  return 1
end

function OnDragStarCard(dwID, dwCmdID, dwParam, pParam)
  game.starDragItem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropStarCard(dwID, dwCmdID, dwParam, pParam)
  game.starDropItem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function StarcardTempSlotEx(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.sendStarSlotChange(1, appdata, -1)
  return 1
end

function StarcardSavedSlotEx(dwID, dwCmdID, dwParam, pParam)
  SAVE_STARCARD_APPDATA = window.getappdata(dwID)
  if NOW_STARCARD_PAGE == 1 then
    local w = window.create(50061, window.parent(dwID), 0, 0)
  else
    game.sendStarSlotChange(2, SAVE_STARCARD_APPDATA, -1)
  end
  window.trace()
  return 1
end

function StarcardUnEquip(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.sendStarSlotChange(6, appdata, -1)
  SAVE_STARCARD_APPDATA = 0
  return 1
end

function Starcard2LevelUp(dwID, dwCmdID, dwParam, pParam)
  game.sendStarSlotChange(4, SAVE_STARCARD_APPDATA, 1)
  SAVE_STARCARD_APPDATA = 0
  window.destroy(window.parent(dwID))
  return 1
end

function Starcard2Equip(dwID, dwCmdID, dwParam, pParam)
  game.sendStarSlotChange(3, SAVE_STARCARD_APPDATA, -1)
  SAVE_STARCARD_APPDATA = 0
  window.destroy(window.parent(dwID))
  return 1
end

function StarcardLevelup2Saved(dwID, dwCmdID, dwParam, pParam)
  game.sendStarSlotChange(8, 1, -1)
  return 1
end
