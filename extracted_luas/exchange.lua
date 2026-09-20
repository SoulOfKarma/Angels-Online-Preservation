WND_EXCHANGE = 0
WND_EXCHANGE_X = 0
WND_EXCHANGE_Y = 0
WND_EXCHECK = 0

function CreateExchangeWnd()
  if window.isexist(WND_EXCHANGE) then
    window.destroy(WND_EXCHANGE)
    WND_EXCHANGE = 0
    return
  end
  WND_EXCHANGE = window.create(27701, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_EXCHANGE_X or 0 > WND_EXCHANGE_Y then
    window.move(WND_EXCHANGE, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_EXCHANGE, WND_EXCHANGE_X, WND_EXCHANGE_Y)
  end
  window.regsetting(WND_EXCHANGE, "WND_EXCHANGE")
  return 1
end

function CloseWordPrize(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_EXCHANGE)
  WND_EXCHANGE = 0
  return 1
end

function OnExchangeItemTooltip(dwID, dwCmdID, dwParam, pParam)
  game.exchangeitemtooltip(dwParam, pParam)
  return 1
end

function CreateCheckExWnd(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_EXCHECK) then
    window.destroy(WND_EXCHECK)
    WND_EXCHANGE = 0
  end
  WND_EXCHECK = window.create(27709, WND_EXCHANGE, 0, SYSTEM_HANDLER)
  if 0 > WND_EXCHANGE_X or 0 > WND_EXCHANGE_Y then
    window.move(WND_EXCHECK, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_EXCHECK, WND_EXCHANGE_X, WND_EXCHANGE_Y)
  end
  window.regsetting(WND_EXCHECK, "WND_EXCHECK")
end

function OnCheckExItem(dwID, dwCmdID, dwParam, pParam)
  game.checkexitem()
  return 1
end

function OnExchangeConfirm(dwID, dwCmdID, dwParam, pParam)
  game.exchangeconfirm()
  window.destroy(WND_EXCHECK)
  WND_EXCHECK = 0
  window.destroy(WND_EXCHANGE)
  WND_EXCHANGE = 0
  return 1
end

function OnExchangeCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_EXCHECK)
  WND_EXCHECK = 0
  return 1
end
