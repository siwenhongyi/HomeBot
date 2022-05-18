import os
from typing import List, Union
import bs4
import ddddocr
import requests
from lxml import etree

SystemMessageKeyWord = [
	'系统消息',
	'系统提示',

	'经验',
	'GB',

	'最后一个',
	'只剩1朵',

	'本农场禁止摘取',
	'本农场只有好友才可以摘取！',
	'您成功偷取了',
	'不要太贪心哦！已经不多啦',
	'不需要',
	'暂时',
	'已成熟，不能',
	'分钟后进入'
]
ocr = ddddocr.DdddOcr(show_ad=False)


def get_res(name):
	"""
	:param name: image name
	:return: res of image ocr
	:rtype: str
	"""
	text = ''
	retry = 0
	while len(text) != 4 and retry < 3:
		retry += 1
		with open(name, 'rb') as f:
			text = ocr.classification(f.read())
		# print(text)
	return text


def get_system_message(content: Union[str, bytes]) -> List[str]:
	"""
	:param content: html string or bytes
	:return: get system message list by xpath
	:rtype: List[str]
	"""
	if isinstance(content, str):
		content = content.encode('utf-8')
	tree = etree.HTML(content)
	texts = tree.xpath('/html/body/text()')
	system_message = []
	for text in texts:
		msg = str(text).replace('\n', '').replace('\r', '').replace('\t', '').replace(' ', '')
		if len(msg) == 0:
			continue
		if msg[0] == ':':
			system_message.append(msg)
		elif any((
				keyword in msg for keyword in SystemMessageKeyWord
		)):
			system_message.append(msg)
	while system_message and system_message[-1] == '':
		system_message.pop()
	if len(system_message) == 1:
		system_message = system_message[0]
	return system_message


def get_novel(book_id=956):
	base_url = 'https://www.netxsw.com'
	params = {'bookid': book_id}
	headers = {
		'Cookie':
			'PHPSESSID=2f4bab1c05f8f22dbbaf4baecd63a65f;'
			'AUTHID=o4G4cmbhrmxwFCb8jpf27iGN7rqKoCjS;'
			'chapter_theme=%7B%22theme%22%3A1%2C%22fontfamily%22%3A1%2C%22fontsize%22%3A16%7D;',
		'x-requested-with': 'XMLHttpRequest',
		'accept': 'application/json, charset=utf-8',
	}
	chapter_path = '/chapter/list.html'
	_session = requests.session()
	chapters = _session.get(base_url + chapter_path, params=params, headers=headers)
	chapters.encoding = 'utf-8'
	chapters = chapters.json()
	chapter_path = '/chapter/index%d-{}.html' % book_id
	index = 1
	book_name = ''
	f = None
	for chapter in chapters['data']:
		print('正在获取第%d章' % index)
		rel_path = chapter_path.format(chapter['id'])
		resp = _session.get(base_url + rel_path)
		resp.encoding = 'utf-8'
		soup = bs4.BeautifulSoup(resp.text, 'html.parser')
		chapter_contents = soup.select('#content-box > section > li.chapter-content')[0]
		if not book_name:
			book_name = soup.select('#content-box > div:nth-child(1) > a')[0].text
		if f is None:
			f = open('%s.txt' % book_name, 'w')
		f.write('{} {}\n'.format(chapter['chapter'], chapter['title']))
		for content in chapter_contents.children:
			if type(content) == bs4.element.NavigableString:
				f.write(str(content))
			elif content.text != '':
				f.write(content.text + '\n')
		index += 1
	f.close()
