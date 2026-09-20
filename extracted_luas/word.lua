WND_WORD_PRIZE = 0
WND_WORD_PRIZE_X = 120
WND_WORD_PRIZE_Y = 100
WORD_PRIZE_ONLY = false

function CloseWordPrize(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_WORD_PRIZE)
  WND_WORD_PRIZE = 0
  return 1
end

function OnSetWordBuyValue(dwID, dwCmdID, dwParam, pParam)
  game.setwordbuyvalue(window.parent(dwID), true)
  return 1
end

function OnWordBuyEx(dwID, dwCmdID, dwParam, pParam)
  game.wordbuyex(window.parent(dwID), dwParam)
  game.setwordbuyvalue(window.parent(dwID), false)
  return 1
end

function OnWordBuyEdit(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, -1)
  game.setwordbuyvalue(window.parent(dwID), false)
  return 1
end

function OnWordBuyScroll(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, dwParam)
  game.setwordbuyvalue(window.parent(dwID), false)
  return 1
end

function OnWordBuy(dwID, dwCmdID, dwParam, pParam)
  game.wordbuy(window.parent(dwID))
  return 1
end

function OnCheckWordPrizeOnly(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    WORD_PRIZE_ONLY = true
  else
    WORD_PRIZE_ONLY = false
  end
  game.updatewordprizewnd()
  return 1
end

function OnWordBuyConfirm(dwID, dwCmdID, dwParam, pParam)
  game.wordbuyconfirm(window.parent(dwID))
  return 1
end

function OnWordBuyCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end
