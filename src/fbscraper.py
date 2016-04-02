#coding:utf-8
from datetime import datetime
import requests
import urllib
import csv
import xmltodict 
import re
import numpy
import sys
reload(sys)
sys.setdefaultencoding(sys.stdout.encoding)
#ksys.setdefaultencoding("cp936")



class FBCrawler:
	def __init__(self, mode):
		self.mode = mode
		self.payload = {}
		self.inputfile = ""
		self.outputfile = ""
		self.proxies = {}
		self.page_ids = []
		self.readConf()
		self.post_out = open("out/post_"+self.outputfile, 'wb')
		self.homepage_out = open("out/homepage_"+self.outputfile, 'wb')
		self.homepage_writer = csv.writer(self.homepage_out) 
		self.post_writer = csv.writer(self.post_out)
		self.post_writer.writerow(['Owner','Homepage','created_time','sharedposts','likes','comments','is_repost'])
		self.homepage_writer.writerow(['Owner','Homepage','likes','mean_post_shares','mean_post_likes','mean_post_comments', 'total_posts'])
		self.flag = False

	def readConf(self):
		conf = open("conf/crawler.xml")
		xmldoc = xmltodict.parse(conf.read())
		self.payload = dict(xmldoc["data"]["payload"])
		self.inputfile = 'in/' + xmldoc["data"]["inputFile"]
		if self.mode == 'link':
			self.readTargetLink()
		elif self.mode == 'pname':
			self.readTargetName()
		elif self.mode == 'name':
			self.readTargets()
		else:  
			print "Invalid mode!!!"
			return
		self.outputfile = xmldoc["data"]["outputFile"]
		if xmldoc['data']['proxies'] != None:
			self.proxies = dict(xmldoc["data"]["proxies"])
		else: self.proxies = {}
		self.confirm()



	def interact(self):
		while self.flag == False:
			option = raw_input("\n\nConfigure payload:\n1)Since\n2)Until\n3)input filename\n4)output filename\n5)token\ns)start query\n7)reload configurations\nq)quit\n\n").strip()
			if option == '1':
				 self.setPayload("since","Grab posts created since:")
			elif option =='2':
				 self.setPayload("until", "Grab posts created before:")
			elif option == '3': 
				self.setFileName(True)
			elif option == '4':
				self.setFileName(False)
			elif option == '5': 
				self.setPayload("access_token", "Please input access token: ")
			elif option == 's':
				 self.startQuery()
			elif option == '7':
				self.readConf()
			elif option =='q': 
				self.setFlag()
			else:
				pass

	def startQuery(self):
		self.confirm()
		c = raw_input("Confirm settings again:(input y/n)")
		if c == 'y' or c == 'Y':
			for page_id in self.page_ids:
				row = self.getPosts(page_id)
				if row != None:
					self.homepage_writer.writerow(row)

	def printError(self,filename, info, details):
		with open('out/' + filename,'a') as efile:
			efile.write("Error:%s\n" % info)
			efile.write("Details:%s\n" % details)
			efile.write("="*100)
			efile.write("\n\n")

	def getPosts(self, page_id):
		url = "https://www.facebook.com/"+page_id
		get_url = "https://graph.facebook.com/v2.5/"+ page_id
		r = requests.get(get_url,params = self.payload, proxies = self.proxies, verify=False)
		rtn = r.json()
		try:
			owner = rtn["name"].encode('utf-8')
		except KeyError as e:
			print "Error occurs when parsing %s" % page_id, rtn
			self.printError("page_id_error.txt", page_id, rtn)
			return None
		print "Start parsing %s's homepage" % owner
		r = requests.get(get_url+"/posts", params=self.payload, proxies = self.proxies, verify=False)
		if r.status_code == 200:
			print "linking to %s" % get_url
			row = [owner,url]
			posts = r.json()
			self.payload["fields"]="likes.summary(true)"
			r = requests.get(get_url, params=self.payload, proxies = self.proxies, verify=False)
			if r.status_code != 200:
				print "Connection error!"
				self.printError("connection_error.txt","Page_id:%s"%page_id,r)
				return None
			data = r.json()
			del self.payload["fields"]
			fav = data["likes"]
			row.append(fav)
			stats = self.parseData(posts, owner, url)
			if stats != None:
				row.extend(stats)
			else:
				return None
			print "Finish scrapping %s's homepage" % owner, row
			return row
		else:
			print "Error occurs when parsing %s's official page." % page_id
			self.printError("connection_error.txt", "Page_id:%s"%page_id, r.json())
			return None

	def parseData(self, data, owner, link):
		buf = dict(data)
		posts = buf["data"]
		count = len(posts)
		page_next = None
		matrix = []

		while count  != 0:
			if count == int(self.payload["limit"]):
				page_next = buf["paging"]["next"]
			else:
				page_next = None
			for message in posts:
				row = [owner, link ]
				post_id = message["id"]
				created =  message["created_time"]
				row.append(created.replace('T',' '))
				stats = self.insights(post_id)
				for i, item in enumerate(stats):
					row.append(item)
				if row[-3] == 0:
					row.append('T')
				else: row.append('F')
				print row
				self.post_writer.writerow(row)
				matrix.append(stats)

			if page_next == None: break
			r = requests.get(page_next,proxies = self.proxies, verify=False)
			if r.status_code == 200:
				print "feching next page"
				buf = dict(r.json())
				posts = buf["data"]
				count = len(posts)
				print count
			else: count = 0

		if len(matrix) != 0:
			matrix = numpy.array(matrix)
			print matrix
			mean =  matrix.astype(float).mean(axis=0).tolist()
			mean.append(len(matrix))
			print mean
			return mean
		else:
			self.printError("homepage_data_error.txt", owner, matrix)
			return None

	def insights(self,post_id):
		url = "https://graph.facebook.com/v2.5/%s?fields=shares.summary(true),likes.summary(true),comments.summary(true)" % post_id
		r = requests.get(url, params = self.payload,proxies = self.proxies, verify=False)
		if r.status_code == 200:
			data = r.json()
			likesCount = data["likes"]["summary"]["total_count"]
			commentsCount = data["comments"]["summary"]["total_count"]
			if data.get("shares") == None:
				shareCount = 0
			else: shareCount = data["shares"]["count"]
			return [shareCount, likesCount, commentsCount]
		else:
			print "Connection error!"
			self.printError("connection_error.txt", 'Post_id:%s'%post_id, r.json())
			return None
		

	def confirm(self):
		print "Input Filename:" + self.inputfile
		print "Output Filename:" + self.outputfile
		print "Proxies:" ,self.proxies
		print "\nPaylod:"
		print self.payload
		print "\nTargets:"
		print self.page_ids

	def readTargets(self):
		f = open(self.inputfile)
		names = [line.strip() for line in f.readlines()]
		for name in names:
			name = unicode(name)
			url = "https://graph.facebook.com/v2.5/search?q=%s&type=page" % name
			name = name.encode("utf-8")
			r = requests.get(url,params = self.payload, verify=False)
			if r.status_code == 200:
				try:
					data = r.json()["data"]
					if len(data) == 0:
						details = "Searching username: %s returns 0 results" %name
						print details
						self.printError("username_not_found_error.txt",name, details)
					else: 
						cflag = False
						for i in range(len(data)):
							try:
								cid = data[i]["id"]
								print "print searching cid: %s" % cid
								r = requests.get("https://graph.facebook.com/v2.5/%s/posts"%cid, params=self.payload,proxies = self.proxies, verify=False)
								data = r.json()["data"]
								if len(data) > 0:
									self.page_ids.append(cid)
									print "Found page_id for username: %s page_id:%s" %(name, cid)
									cflag = True
									break
							except:
								pass
						if cflag == False:
							self.printError("username_not_found_error.txt",name,r.json())		
				except Exception as e:
					details = "Exception occurs when parsing usename %s" %name
					print details
					self.printError("username_not_found_error.txt",name,details)
					pass
			else:
				print "Connection Eccor occurs when parsing username: %s" % name
				self.printError("connection_error.txt","Username:%s"%name, r.json())
		with open("ids.txt",'w') as w:
			for l in self.page_ids:
				w.write(l+'\n')


	def readTargetLink(self):
		f = open(self.inputfile)
		links = [line.strip() for line in f.readlines()]
		for link in links:
			url = "https://graph.facebook.com/v2.5/?ids=%s" % link
			r = requests.get(url, params=self.payload, proxies = self.proxies, verify=False)
			data = r.json()
			link = urllib.unquote(link).decode('utf8')	
			cid = data[link]["id"]
			print "Parse link %s to  id: %s" % (link, cid)
			self.page_ids.append(cid)
		with open("out/ids.txt",'w') as wfile:
			for l in self.page_ids:
				wfile.write(l+'\n')

	def readTargetName(self):
		f = open(self.inputfile)
		self.page_ids = [line.strip() for line in f.readlines()]

	def setPayload(self,field, hint):
		self.payload[field] = raw_input(hint).strip()
		self.saveConf()
				
	def setFileName(self, is_input):
		if is_input == True:
			self.inputfile = raw_input("Please enter filename:")
			self.readTargetName()
		else: self.outputfile = raw_input("Please enter filename:")

		self.saveConf()
	

	def saveConf(self):
		f = open('crawler.xml','w')
		f.write('<data>\n\t<payload>\n')
		for k,v in self.payload.iteritems():
			f.write('\t\t<%s>%s</%s>\n'%(k,v,k))
		f.write("\t</payload>\n\t<inputFile>%s</inputFile>\n\t<outputFile>%s</outputFile>\n\t<proxies>\n"%(self.inputfile,self.outputfile))
		for k,v in self.proxies.iteritems():
			f.write('\t\t<%s>%s</%s>\n'%(k,v,k))
		f.write('\t</proxies>\n')
		f.write('</data>')
		f.close()
		 
	def setFlag(self):
		self.flag = True


	def close(self):
		self.post_out.close()
		self.homepage_out.close()
		print "Exiting fbcrawler.."

if __name__== "__main__":
	while True:
		itype =  raw_input("choose input format(link/pname/name):").strip()
		if itype != "link" and itype != "pname" and itype != "name" :
			print "Wrong input!"
		else:
			break
	c = FBCrawler(itype)
	c.interact()
	c.close()
	print "End of program."
