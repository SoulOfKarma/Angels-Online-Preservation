function OnTrade_Invite(dwID, dwCmdID, dwParam, pParam)
  game.tradeinvite()
  
  return 1
end

function OnTradeInvite_OK(dwID, dwCmdID, dwParam, pParam)
  game.tradeinviteok(dwID)
  return 1
end

function OnTradeInvite_Cancel(dwID, dwCmdID, dwParam, pParam)
  game.tradereject(window.find(window.parent(dwID), 3076))
  return 1
end

function OnTrade_Drop(dwID, dwCmdID, dwParam, pParam)
  game.tradedrop(dwID, pParam)
  return 1
end

function OnTrade_Confirm(dwID, dwCmdID, dwParam, pParam)
  window.enable(dwID, false)
  game.tradesetok()
  return 1
end

function OnTrade_Cancel(dwID, dwCmdID, dwParam, pParam)
  game.tradeclose()
  window.destroy(WND_TRADE)
  WND_TRADE = 0
  return 1
end

function OnTrade_Trade(dwID, dwCmdID, dwParam, pParam)
  game.tradetrade()
  return 1
end

function OnTrade_Money(dwID, dwCmdID, dwParam, pParam)
  game.trademoney()
  return 1
end

function OnTrade_Money_Edit(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, -1)
  return 1
end

function OnTrade_Money_Scroll(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, dwParam)
  return 1
end

function OnTrade_Money_OK(dwID, dwCmdID, dwParam, pParam)
  local Money = window.gettitle(window.find(WND_TRADE, 3133))
  window.settitle(window.find(WND_TRADE, 3068), Money)
  window.destroy(window.parent(dwID))
  game.trademoneyok(Money)
  return 1
end

function OnTrade_Money_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end
