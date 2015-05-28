#import tracker
import multiprocessing
import socket, json, file
from threading import Thread, Lock


#from random import randint
buffer_size = 65536

# max 65536 Bytes
mutex = Lock()

max_threads = multiprocessing.cpu_count()

class Peer():
	"""docstring for Peer"""
	__address = None
	__speed_download = None
	__speed_upload = None
	__trackers = None
	__files_upload = None
	__files_download = None
	__socket_peer_download = None
	__socket_peer_upload = None
	__parts_requested = None
	__peers_sleep = {}

	def __init__(self, address = None, trackers = []):
		self.__address = address
		self.__speed_download = 0.0
		self.__speed_upload = 0.0
		self.__files_download = {}
		self.__files_upload = {}
		self.__trackers = trackers
		self.__parts_requested = {}
	def __eq__(self, peer):
		return self.__address.get_ip() == peer.__address.get_ip()

	def run(self):
		self.__socket_peer_download = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.__socket_peer_upload = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		

	# Path references .pytorrent
	def download(self, path):
		print "Download"
		th=Thread( target=self.download_thread,
					args = ( path, ) )
		th.start()
		
	def download_thread(self, path):
		print "Download Thread"
		f = file.File(path)
		if f.is_complete():
			if f.exist():
				print "Arquivo completo"
				return
			else:
				f.merge()
				return
		#se o arquivo existir
		if f.exist():
			print "Arquivo ja existe"
			return
	
		hash_file = f.get_hash()
		
		if hash_file == None:
			print "Morreu"
			return
		
		self.__files_download[hash_file] = f
		#para cada uma das partes
		message = json.dumps({"type":3, "file": hash_file})
		#para cada um dos trackers
		for k in self.__trackers:
			self.__socket_peer_download.sendto(message, (k.get_address().get_ip(),k.get_address().get_port()))
			print "Peer download- eu " + str(self.__socket_peer_download.getsockname()) + " pedir ao tracker " + str(k.get_address()) + "a lista dos peer dese arquivo"
		while 1:
			#response in 30
			message, tracker_address = self.__socket_peer_download.recvfrom(buffer_size)
			print "Peer download- eu " + str(self.__socket_peer_download.getsockname()) + " recebi do tracker" + str(tracker_address) + "a lista dos peers"
			try:
				message = json.loads(message)
				th=Thread( target=self.download_part_thread,
							args = (path, hash_file, f.get_parts() ,  message ) )
				th.start()
			except:
				print "Falha ao carregar a resposta"
				continue
			if f.exist():
				return
			#break
	def download_part_thread(self,path, hash_file, parts, message):
		print "Download Part Thread"
		#try:
		peers = message["address_peers"]
		#except:
		#	print "Sem Addres Peers"
		#	return
		for i in parts.values():
			hash_part = i.get_hash()
			msn = json.dumps({"type": 1,"file": hash_file, "part" : hash_part})
			socket_cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			threads_download = []
			for k in peers:
				socket_cliente.sendto(msn, (k[0], k[1]) )
			print "Peer download: "+ str(socket_cliente.getsockname()) +"  requisitei ao peer " + str(i) + "um data de uma parte"
			th=Thread( target=self.download_part_peer,
						args = ( path, hash_file,hash_part, socket_cliente) )
			th.start()
			threads_download.append(th)
			if len(threads_download) >= max_threads:
				for i in threads_download:
					i.join()

	def download_part_peer(self,path, hash_file, hash_part, socket_cliente):
		print "Entrando na Thread Download Par Peeer!!! \n"
		f = file.File(path.replace(".pytorrent", ""))
		while 1:
			if f.exist():
				print "File ja existe"
				break
			message, peer_address = socket_cliente.recvfrom(buffer_size)
			print "Pee download, "+ str(socket_cliente.getsockname()) +" recebi do peer " + str(peer_address) + "um arquivo"
			try:
				message = json.loads(message)
				self.__peers_sleep[peer_address] = message
				print "continue"
				continue
			except:
				print "pegando adata"
				data = message
				message = self.__peers_sleep[peer_address]	
			f.data_to_part(data)
			
			mutex.acquire()
			if f.is_complete():
				print "Download Completo!!! \n"
				if f.exist():
						print "Arquivo ja existe!!!!\n"
						break
				print "Chamou merge em download_part_peer completo"
				if f.merge() == False:
					print "*******************Erro ao fazer o merge ****************"
				else:
					print "*************Arquivo baixado com exito **************"
				mutex.release()
				break
			mutex.release()





	def upload(self, path):
		th=Thread( target=self.upload_thread,
					args = ( path, ) )
		th.start()
	def upload_thread(self, path):
		f = file.File(path)
		self.__files_upload[f.get_hash()] = f
		f.divider_parts()
		message = json.dumps({"type": 2, "file": f.get_hash()})
		for k in self.__trackers:
			self.__socket_peer_upload.sendto(message, (k.get_address().get_ip(),k.get_address().get_port()))
			print "Peer upload : Eu "+  str(self.__address) +"  mandei um arquivo pro tracker " + str(k.get_address())
		while 1:
			message, peer_address = self.__socket_peer_upload.recvfrom(buffer_size)
			message = json.loads(message)
			if int(message["type"]) == 1:
				print "Peer upload : Eu " + str(self.__address) + "recebi do Peer " + str(peer_address) + "um pedido de arquivo"
				th=Thread( target=self.upload_part_thread,
						args = ( message["file"], message["part"], peer_address))
				th.start()
			else:
				print "Peer upload: "+ str(self.__address) +", O Tracker " + str(peer_address) + "confirmou o recebimento do meu upload"

	def upload_part_thread(self,hash_file, hash_part, address):
		try:
			print "Files que eu estou upando" + str(self.__files_upload.keys())
			f = self.__files_upload[hash_file]
		except:
			return 
		try:
			data = f.part_to_data_in_parts(hash_part)
		except:
			return
		import sys
		response = json.dumps({"type": 10, "file": hash_file, "part" : hash_part})
		print "Tamanho para enviar depois do dumps = " + str(sys.getsizeof(response))
		self.__socket_peer_upload.sendto(response, address)
		self.__socket_peer_upload.sendto(data, address)

		print "Peer upload: Eu " + str(self.__address) + "respondi com a parte ao peer " + str(address)


	def set_address(self, address):
		self.__address = address
	def  get_address(self):
		return self.__address

	def get_speed_download(self):
		return self.__speed_download
	def get_speed_upload(self):
		return self.__speed_upload

	def update_speed_download(self):
		pass
	def update_speed_upload(self):
		pass

	def update_spped_statistics(self):
		pass

	def add_tracker(self, tracker):
		try:
			self.__trackers.append(tracker)
			return True
		except:
			return False
	def rem_tracker(self, tracker):
		try:
			self.__trackers.remove(tracker)
			return True
		except:
			return False