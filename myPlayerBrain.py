"""
 * ----------------------------------------------------------------------------
 * "THE BEER-WARE LICENSE" 
 * As long as you retain this notice you can do whatever you want with this 
 * stuff. If you meet an employee from Windward some day, and you think this
 * stuff is worth it, you can buy them a beer in return. Windward Studios
 * ----------------------------------------------------------------------------
"""

import random as rand
import traceback
import simpleAStar
from framework import sendOrders, playerPowerSend

NAME = "We, The People 3294872349"

SCHOOL = "Harvey Mudd College"

class MyPlayerBrain(object):
    """The Python AI class.  This class must have the methods setup and gameStatus."""
    def __init__(self, name=NAME):
        self.name = name #The name of the player.
        
        #The player's avatar (looks in the same directory that this module is in).
        #Must be a 32 x 32 PNG file.
        try:
            avatar = open("MyAvatar.png", "rb")
            avatar_str = b''
            for line in avatar:
                avatar_str += line
            avatar = avatar_str
        except IOError:
            avatar = None # avatar is optional
        self.avatar = avatar
    
    def setup(self, gMap, me, allPlayers, companies, passengers, client, stores, powerUpDeck, framework):
        """
        Called at the start of the game; initializes instance variables.

        gMap -- The game map.
        me -- Your Player object.
        allPlayers -- List of all Player objects (including you).
        companies -- The companies on the map.
        passengers -- The passengers that need a lift.
        client -- TcpClient to use to send orders to the server.
        stores -- All the coffee stores.
        powerUpDeck -- The powerups this player has in their hand (may have to wait before playing it).
        powerUpHand -- The powerups this player can draw.
        myPassenger -- The passenger currently in my limo, none to start.
        MAX_TRIPS_BEFORE_REFILL -- The maximum number of trips allowed before a refill is required.
        
        """
        self.framework = framework
        self.gameMap = gMap
        self.players = allPlayers
        self.me = me
        self.companies = companies
        self.passengers = passengers
        self.client = client
        self.stores = stores
        self.powerUpDeck = powerUpDeck
        self.powerUpHand = []
        self.powerUpHand2 = []
        self.myPassenger = None
        self.MAX_TRIPS_BEFORE_REFILL = 3

        self.pickup = pickup = self.allPickups(me, passengers)

        # get the path from where we are to the dest.

        path = self.calculatePathPlus1(me, pickup[0].lobby.busStop)
        sendOrders(self, "ready", path, pickup)

    def setOkToPlay(self):
        for p in self.powerUpHand2:
            p.okToPlay = True

    def gameStatus(self, status, playerStatus):
        """
        Called to send an update message to this A.I.  We do NOT have to send a response.

        status -- The status message.
        playerStatus -- The player this status is about. THIS MAY NOT BE YOU.
        players -- The status of all players.
        passengers -- The status of all passengers.

        """

        if self.me.score < 0.5:
            self.setOkToPlay()

        # bugbug - Framework.cs updates the object's in this object's Players,
        # Passengers, and Companies lists. This works fine as long as this app
        # is single threaded. However, if you create worker thread(s) or
        # respond to multiple status messages simultaneously then you need to
        # split these out and synchronize access to the saved list objects.

        try:
            # bugbug - we return if not us because the below code is only for
            # when we need a new path or our limo hits a bus stop. If you want
            # to act on other players arriving at bus stops, you need to
            # remove this. But make sure you use self.me, not playerStatus for
            # the Player you are updating (particularly to determine what tile
            # to start your path from).
            if playerStatus != self.me:
                if(status == "PASSENGER_DELIVERED_AND_PICKED_UP" or
                  status == "PASSENGER_PICKED_UP"):

                    if(playerStatus.limo.passenger == self.me.pickup[0] and self.me.limo.coffeeServings > 0):
                        pickup = self.allPickups(self.me, self.passengers)
                        print "Changing targets because someone else picked up ours"
                        print "Now picking up"
                        print pickup[0]
                        ptDest = pickup[0].lobby.busStop
                        self.displayOrders(ptDest)
            
                        # get the path from where we are to the dest.
                        path = self.calculatePathPlus1(self.me, ptDest)

                        sendOrders(self, "move", path, pickup)
                    elif (self.me.limo.coffeeServings <= 0):
                        print "Gotta get more coffee"
                        path = self.calculatePathPlus1(self.me, self.findClosestStore().busStop)
                        pickup = self.allPickups(self.me, self.passengers)
                        sendOrders(self, "move", path, pickup)
                return

            ptDest = None
            pickup = []
            
            if (status == "UPDATE" and self.me.limo.coffeeServings > 0):
                self.maybePlayPowerUp()
                if(self.me.limo.passenger): #if passenger in limo
                    if(self.enemyAtDestination(self.me.limo.passenger)):
                        print "enemy deposited at destination, changing passenger"
                        pickup = self.allPickups(self.me, self.passengers)
                        ptDest = pickup[0].lobby.busStop
                        self.displayOrders(ptDest)
            
                        # get the path from where we are to the dest.
                        path = self.calculatePathPlus1(self.me, ptDest)

                        sendOrders(self, "move", path, pickup)
                elif (self.me.limo.coffeeServings <= 0): #no passenger in limo
                    print "No passenger in limo. Heading for "
                    print self.me.pickup[0]
            elif (self.me.limo.coffeeServings <= 0):
                print "Gotta get more coffee"
                path = self.calculatePathPlus1(self.me, self.findClosestStore().busStop)
                pickup = self.allPickups(self.me, self.passengers)
                sendOrders(self, "move", path, pickup)

                return
            
            self.displayStatus(status, playerStatus)
            
            print "status:"
            print status
            
            if (status == "PASSENGER_NO_ACTION" or status == "NO_PATH"):
                if self.me.limo.passenger is None:
                    pickup = self.allPickups(self.me, self.passengers)
                    ptDest = pickup[0].lobby.busStop
                    print "Now picking up"
                    print pickup[0]
                else:
                    ptDest = self.me.limo.passenger.destination.busStop
            elif (status == "PASSENGER_DELIVERED" or
                  status == "PASSENGER_ABANDONED"):
                pickup = self.allPickups(self.me, self.passengers)
                ptDest = pickup[0].lobby.busStop
                self.setOkToPlay()
            elif  status == "PASSENGER_REFUSED_ENEMY":
                pickup = self.allPickups(self.me, self.passengers)
                ptDest = pickup[0].lobby.busStop
                self.setOkToPlay()
            elif (status == "PASSENGER_DELIVERED_AND_PICKED_UP" or
                  status == "PASSENGER_PICKED_UP"):
                pickup = self.allPickups(self.me, self.passengers)
                ptDest = self.me.limo.passenger.destination.busStop
                self.setOkToPlay()
                
            # coffee store override
            if(status == "PASSENGER_DELIVERED_AND_PICKED_UP" or status == "PASSENGER_DELIVERED" or status == "PASSENGER_ABANDONED"):
                if(self.me.limo.coffeeServings <= 0):
                    ptDest = self.findClosestStore().busStop
                self.setOkToPlay()
            elif(status == "PASSENGER_REFUSED_NO_COFFEE" or status == "PASSENGER_DELIVERED_AND_PICK_UP_REFUSED"):
                ptDest = self.findClosestStore().busStop
                self.setOkToPlay()
            elif(status == "COFFEE_STORE_CAR_RESTOCKED"):
                pickup = self.allPickups(self.me, self.passengers)
                if len(pickup) != 0:
                    ptDest = pickup[0].lobby.busStop
                self.setOkToPlay()
            
            if(ptDest == None):

                return
            
            self.displayOrders(ptDest)
            
            # get the path from where we are to the dest.
            path = self.calculatePathPlus1(self.me, ptDest)
            sendOrders(self, "move", path, pickup)
        except Exception as e:
            print traceback.format_exc()
            raise e

    def displayOrders(self, ptDest):
        msg = None
        potentialStores = [s for s in self.stores if s.busStop == ptDest]
        store = None
        if len(potentialStores) > 0:
            store = potentialStores[0]
        if store is not None:
            storename = store.name
            if "Gloria Jean" in storename:
                storename = "Gloria Jean's Coffees"
            if "Peet" in storename:
                storename = "Peet's Coffee and Tea"
            if "Tully" in storename:
                storename = "Tully's Coffee"
            msg = "Heading toward {0} at {1}".format(storename, ptDest)
        else:
            potentialCompanies = [c for c in self.companies if c.busStop == ptDest]
            company = None
            if len(potentialCompanies) > 0:
                company = potentialCompanies[0]
            if company is not None:
                msg = "Heading toward {0} at {1}".format(company.name, ptDest)
        if msg is not None:
            print(msg)

    def calculatePathPlus1 (self, me, ptDest):
        path = simpleAStar.calculatePath(self.gameMap, me.limo.tilePosition, ptDest)
        # add in leaving the bus stop so it has orders while we get the message
        # saying it got there and are deciding what to do next.
        if len(path) > 1:
            path.append(path[-2])
        return path
    
    def checkForRaces(self):
        playersWithoutPassengers = filter(lambda p: p.guid != self.me.guid and p.limo.passenger is None, self.players)
        if (self.me.limo.passenger == None):
            for player in playersWithoutPassengers:
                if ((player.limo.path != []) and (self.me.limo.path != [])):
                    if (player.limo.path[-1] == self.me.limo.path[-1]):
                        return player
        return None

    def maybePlayPowerUp(self):
        
        # not enough, draw
        if len(self.powerUpHand2) < self.me.maxCardsInHand and len(self.powerUpDeck) > 0:
            for card in self.powerUpDeck:
                if(len(self.powerUpHand2) >= self.me.maxCardsInHand):
                    break
                # select a card
                self.powerUpDeck.remove(card)
                self.powerUpHand2.append(card)
                playerPowerSend(self, "DRAW", card)
            #return
        print "Length of hand", len(self.powerUpHand2)
        print "Max length", self.me.maxCardsInHand

        # can we play one?
        okToPlayHand = filter(lambda p: p.okToPlay, self.powerUpHand2)
        print "Ok to play len", len(okToPlayHand)
        if len(okToPlayHand) == 0:
            return

        for powerUp in okToPlayHand:
            print "Looking at powerUp ", powerUp.card
            if powerUp.card == "ALL_OTHER_CARS_QUARTER_SPEED":
                playerPowerSend(self, "PLAY", powerUp)
                self.powerUpHand2.remove(powerUp)

            elif powerUp.card == "MOVE_PASSENGER":
                currPassenger = self.me.limo.passenger
                if currPassenger != None:
                    # Could try waiting until right before we arrive at destination to use
                    # Although if there are multiple enemies, could stop us from getting rid
                    # of all of them
                    for e in currPassenger.enemies:
                        if e.lobby == currPassenger.destination:
                            powerUp.passenger = e
                            playerPowerSend(self, "PLAY", powerUp)
                            self.powerUpHand2.remove(powerUp)
                            break
            elif powerUp.card == "STOP_CAR":
                # Check for races:
                playersWithoutPassengers = filter(lambda p: p.guid != self.me.guid and p.limo.passenger is None, self.players)
                racingPlayer = self.checkForRaces()
                if racingPlayer != None:
                    powerUp.player = racingPlayer
                    print "stopping", racingPlayer, " their destination:", racingPlayer.limo.path[-1], "our dest", self.limo.path[-1]
                   
                # Stop best player if we have not found a race
                else:
                    bestScore = 0
                    bestPlayer = None
                    for player in self.players:
                        if player.totalScore > bestScore:
                            bestScore = player.totalScore
                            bestPlayer = player
                    powerUp.player = bestPlayer

                playerPowerSend(self, "PLAY", powerUp)
                self.powerUpHand2.remove(powerUp)

            elif powerUp.card == "CHANGE_DESTINATION":
                playersWithPassengers = filter(lambda p: p.guid != self.me.guid and p.limo.passenger is not None, self.players)
                for player in playersWithPassengers:
                    # If a player is between 3 and 10 spaces away from destination
                    if  (10 > abs(player.limo.tilePosition[0] - player.limo.path[-1][0]) > 3) or (10 > abs(player.limo.tilePosition[1] - player.limo.path[-1][1]) > 3):
                        powerUp.player = player
                        playerPowerSend(self, "PLAY", powerUp)
                        self.powerUpHand2.remove(powerUp)
                        break

            else:
                playerPowerSend(self, "DISCARD", powerUp)
                self.powerUpHand2.remove(powerUp)
            #playerPowerSend(self, "PLAY", powerUp)
            
        return
    
    # A power-up was played. It may be an error message, or success.
    def powerUpStatus(self, status, playerPowerUp, cardPlayed):
        # redo the path if we got relocated
        if((status == "POWER_UP_PLAYED") and ((cardPlayed.card == "RELOCATE_ALL_CARS") or ((cardPlayed.card == "CHANGE_DESTINATION") and (cardPlayed.player.guid == self.me.guid)))):
            self.gameStatus("NO_PATH", self.me)
        return
    
    def displayStatus(self, status, plyrStatus):
        msg = ""
        # Sometimes, myPassenger or myPassenger.lobby is None. If you want to figure this
        # out on your own, have at it, but it really only affects the messages displayed below.
        if(status == "PASSENGER_DELIVERED"):
            if self.myPassenger.name is not None or self.myPassenger.lobby is not None:
                msg = "{0} delivered to {1}\n".format(self.myPassenger.name, self.myPassenger.lobby.name)
            self.myPassenger = None
        elif(status == "PASSENGER_ABANDONED"):
            if self.myPassenger is not None or self.myPassenger.lobby is not None:
                msg = "{0} abandoned at {1}\n".format(self.myPassenger.name, self.myPassenger.lobby.name)
            self.myPassenger = None
        elif(status == "PASSENGER_REFUSED_ENEMY"):
            msg = "{0} refused to exit at {1} - enemy there".format(plyrStatus.limo.passenger.name, plyrStatus.limo.passenger.destination.name)
        elif(status == "PASSENGER_DELIVERED_AND_PICKED_UP"):
            msg = "{0} delivered at {1} and {2} picked up".format(self.myPassenger.name, self.myPassenger.lobby.name, plyrStatus.limo.passenger.name)
            self.myPassenger = plyrStatus.limo.passenger
        elif(status == "PASSENGER_PICKED_UP"):
            msg = "{0} picked up".format(plyrStatus.limo.passenger.name)
            self.myPassenger = plyrStatus.limo.passenger
        elif(status == "PASSENGER_REFUSED_NO_COFFEE"):
            msg = "Passenger refused to board limo, no coffee"
        elif(status == "PASSENGER_DELIVERED_AND_PICK_UP_REFUSED"):
            msg = "{0} delivered at {1}, new passenger refused to board limo, no coffee".format(self.myPassenger.name, self.myPassenger.lobby.name)
        elif(status == "COFFEE_STORE_CAR_RESTOCKED"):
            msg = "Coffee restocked!"
        
        if(msg != ""):
            print (msg)
        return
    
    def allPickups (self, me, passengers):
            # pickup is a list of the possible passengers to pick up.
            pickup = [p for p in passengers if (not p in me.passengersDelivered and
                                                p != me.limo.passenger and
                                                p.car is None and
                                                p.lobby is not None and p.destination is not None and
                                                not any(i for i in p.enemies if i in p.destination.passengers))]
            total = 0
            for passenger in pickup:
                self.calculateScore(passenger)
                total += passenger.score

            rand.shuffle(pickup)
            select = rand.random()*total
            for passenger in pickup:
                select -= passenger.score
                if (select <= 0):
                    pickup.insert(0, pickup.pop(pickup.index(passenger)))
                    break            
            return pickup

    def calculateScore(self, passenger):
        pathScore = self.scorePath(simpleAStar.calculatePath(self.gameMap, self.me.limo.tilePosition, passenger.lobby.busStop))
        pathScore += self.scorePath(simpleAStar.calculatePath(self.gameMap, passenger.lobby.busStop, passenger.destination.busStop))
        passenger.score = passenger.pointsDelivered/float(pathScore)
        if self.enemyAtDestination(passenger):
            passenger.score = 0

    def scorePath(self, path):
        return len(path)

    def findClosestStore(self):
        """Finds closest coffee store"""
        closestStore = self.stores[0]
        score = self.scorePath(self.calculatePathPlus1(self.me, closestStore.busStop))
        for x in self.stores:
            newScore = self.scorePath(self.calculatePathPlus1(self.me, x.busStop))
            if newScore < score:
                score = newScore
                closestStore = x
        return closestStore

    def enemyAtDestination(self, passenger):
        destination = passenger.destination
        for enemy in passenger.enemies:
            if destination == enemy.lobby and destination:
                return True
        return False

