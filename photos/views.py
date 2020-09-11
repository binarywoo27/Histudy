from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from .models import Data, Announcement, Profile, Verification, Year, UserInfo, StudentID, Group
from .forms import DataForm, AnnouncementForm#, ProfileForm

from django.views.generic import ListView
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import auth
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import transaction

from django.db.models import Count, Max, Sum, Subquery, OuterRef
from django.db.models.expressions import RawSQL

#For Code Verification
from datetime import datetime, timedelta
from django.utils import timezone
import json, random

#CSV import
from tablib import Dataset
import pandas
import magic, copy, csv

# for Infinite Scroll
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# for device detection
from django_user_agents.utils import get_user_agent


LOGIN_REDIRECT_URL = '/user_check/'


def current_year():
    return datetime.date.today().year

def current_sem():
    if datetime.date.today().month < 8 and datetime.date.today().month > 1:
        return 1
    else:
        return 2

def detail(request, pk):
    data = get_object_or_404(Data, pk=pk)
    ctx={}
    if request.user.is_authenticated:
        username = request.user.username
        user = request.user
        ctx['userobj'] = user
    else:
        return redirect('loginpage')

    participators = data.participator.all()
    print("detail participators: ", participators)

    ctx = {
        'post': data,
        'username': username,
        'participators': participators,
    }

    now_time = timezone.localtime()
    time_diff = now_time - data.date

    if time_diff.seconds / 3600 < 1 :
        ctx['can_edit'] = True
    else:
        ctx['can_edit'] = False

    return render(request, 'detail.html', ctx)

# For Random Code Generator
all_pins = [format(i, '04') for i in range(1000, 10000)]
possible = [i for i in all_pins if len(set(i)) > 3]

@login_required(login_url=LOGIN_REDIRECT_URL)
def data_upload(request):
    ctx={}

    try:
        user = User.objects.get(pk=request.user.pk)
        ctx['userobj'] = user
        if user.is_staff is True:
            return redirect('userList')
    except User.DoesNotExist:
        return redirect(reverse('loginpage'))

    is_mobile = request.user_agent.is_mobile
    is_tablet = request.user_agent.is_tablet

    now_time = timezone.localtime()

    if user.verification.code_when_saved is None:
        user.verification.code_when_saved = now_time
        verify_code = random.choice(possible)
        user.verification.code = verify_code
        user.save()

    time_diff = now_time - user.verification.code_when_saved

    if (60*10 - time_diff.seconds) > 0:
        ctx['code_time'] = time_diff.seconds
    else:
        ctx['code_time'] = 0

    if request.method == "GET":
        if is_mobile or is_tablet:
            form = DataForm(user=request.user, is_mobile=True)
            form.set_is_mobile()
        else:
            form = DataForm(user=request.user, is_mobile=False)
            form.set_is_mobile()
    elif request.method == "POST":
        form = DataForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            obj = form.save()
            obj.author = user
            # latestid = Data.objects.filter(author=user).order_by('-id')
            # if latestid:
            #     obj.idgroup = latestid[0].idgroup + 1
            # else:
            #     obj.idgroup = 1

            if user.verification.code is not None:
                if (time_diff.seconds)/60 < 10:
                    obj.code = user.verification.code
                    obj.code_when_saved = user.verification.code_when_saved
                    user.verification.code = None
                    user.verification.code_when_saved = None
                else:
                    user.verification.code = None
                    user.verification.code_when_saved = None
                    messages.warning(request, '코드가 생성된지 10분이 지났습니다.', extra_tags='alert')

            # num = user.userinfo.num_posts
            # user.userinfo.num_posts = num + 1
            # user.userinfo.most_recent = obj.date
            # user.userinfo.name = username
            user.save()

            year = current_year()
            try:
                yearobj = Year.objects.get(year=year)
            except:
                yearobj = Year.objects.create(year=year)

            obj.group = user.profile.group
            obj.year = yearobj

            obj.save()
            messages.success(request, '게시물을 등록하였습니다.', extra_tags='alert')
            return HttpResponseRedirect(reverse('main'))
        else:
            messages.warning(request, '모든 내용이 정확하게 입력되었는지 확인해주세요.', extra_tags='alert')

    ctx['form'] = form
    ctx['userobj'] = user

    return render(request, 'upload.html', ctx)


def data_edit(request, pk):
    ctx={}

    if request.user.is_authenticated:
        username = request.user.username
        ctx['username'] = request.user.username
    else:
        return redirect('loginpage')

    if username:
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        if user.is_staff is True:
            return redirect('userList')
    else:
        return redirect('loginpage')

    is_mobile = request.user_agent.is_mobile
    is_tablet = request.user_agent.is_tablet


    # if (60*10 - time_diff.seconds) > 0:
    #     ctx['code_time'] = time_diff.seconds
    # else:
    #     ctx['code_time'] = 0

    # find the target post
    post = Data.objects.get(id=pk)

    if request.method == "GET":
        if is_mobile or is_tablet:
            form = DataForm(user=request.user, is_mobile=True, instance=post)
            form.set_is_mobile()
        else:
            form = DataForm(user=request.user, is_mobile=False, instance=post)
            form.set_is_mobile()
    elif request.method == "POST":
        form = DataForm(request.POST, request.FILES, user=request.user, instance=post)
        if form.is_valid():
            # print(form.cleaned_data)
            post.title = form.cleaned_data['title']
            post.text = form.cleaned_data['text']
            post.participator.set(form.cleaned_data['participator'])
            post.study_start_time = form.cleaned_data['study_start_time']
            post.study_total_duration = form.cleaned_data['study_total_duration']

            post.save()

            messages.success(request, '게시물을 등록하였습니다.', extra_tags='alert')
            return redirect('detail', pk)
        else:
            messages.warning(request, '모든 내용이 정확하게 입력되었는지 확인해주세요.', extra_tags='alert')

    ctx['form'] = form
    ctx['userobj'] = user

    return render(request, 'edit.html', ctx)


def warn_overwrite(request, year_pk, sem):
    ctx={}
    yearobj = Year.objects.get(pk=year_pk)
    userinfo_list = UserInfo.objects.filter(year=yearobj, sem=sem)
    ctx['userinfo_list'] = userinfo_list
    
    if request.method == 'POST':
        imported_data_string = request.session.get('imported_data_string', None)
        imported_data_json = json.loads(imported_data_string)
        imported_data_list = []

        for data in imported_data_json.items():
            value_list = list(data[1].values())
            imported_data_list.append(copy.deepcopy(value_list))

        # but first remove existing userinfo
        
        userinfo_list.delete()

        num_of_ppl = len(data[1])
        for i in range(num_of_ppl):
            groupNo = imported_data_list[0][i]
            stuID = imported_data_list[1][i]

            try:
                groupobj = Group.objects.get(no=groupNo)
            except:
                groupobj = Group.objects.create(no=groupNo)

            try:
                idobj = StudentID.objects.get(student_id=stuID)
            except:
                idobj = StudentID.objects.create(student_id=stuID)

            UserInfo.objects.create(year=yearobj, sem=sem, group=groupobj, student_id=idobj)

        return redirect(reverse('csv_upload'))

    else:
        return render(request, 'warn_overwrite.html', ctx)

    

    
@csrf_exempt
@login_required(login_url=LOGIN_REDIRECT_URL)
def csv_upload(request):
    ctx = {}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        if user.is_staff is False:
            return redirect('main')
    else:
        return redirect('loginpage')

    if request.method == 'POST':
        dataset = Dataset()
        data = request.FILES
        new_usergroup = data['myfile']

        csv_file = copy.deepcopy(new_usergroup)

        blob = csv_file.read()
        m = magic.Magic(mime_encoding=True)
        encoding = m.from_buffer(blob)

        if encoding == "iso-8859-1":
            encoding = "euc-kr"

        imported_data = dataset.load(new_usergroup.read().decode(encoding), format='csv')


        if imported_data is None:
            messages.warning(request, 'CSV파일의 Encoding이 UTF-8이거나 EUC-KR형식으로 변형해주세요.', extra_tags='alert')
            redirect('csv_upload')

        group_no = "1"
        group_list = []

        year = request.POST['year']
        if request.POST['semester'] == 'spring':
            semester = 1
        elif request.POST['semester'] == 'fall':
            semester = 2

        if int(year) < 2000:
            pass # 에러 처리
        else:
            try:
                yearobj = Year.objects.get(year=year)
            except:
                yearobj = Year.objects.create(year=year)


        userinfo_list = UserInfo.objects.filter(year=yearobj, sem=semester)
        if userinfo_list:
            df = pandas.DataFrame(data=list(imported_data))
            request.session['imported_data_string'] = df.to_json()
            return redirect(reverse('warn_overwrite', args=(yearobj.pk, semester)))


        for data in imported_data:
            print("data", data)
            try:
                groupobj = Group.objects.get(no=data[0])
            except:
                groupobj = Group.objects.create(no=data[0])

            try:
                idobj = StudentID.objects.get(student_id=data[1])
            except:
                idobj = StudentID.objects.create(student_id=data[1])

            UserInfo.objects.create(year=yearobj, sem=semester, group=groupobj, student_id=idobj)


            '''

            if group_no == data[0]:
                group_list.append(data)

            else:
                group_list.sort(key=lambda tup: tup[1])

                is_first = 1

                for elem in group_list:
                    if is_first:
                        user_id = "group"+elem[0]
                        user_pw = elem[1]
                        user_email = elem[2]
                        is_first = 0

                    if User.objects.filter(username=user_id).exists():
                        member_student_id = elem[1]
                        member_name = elem[3]
                        member_email = elem[2]
                        Member.objects.create(user=User.objects.get(username=user_id), student_id = member_student_id, name = member_name, email = member_email)
                    else:
                        user = User.objects.create_user(username=user_id,
                                            email=user_email,
                                            password=user_pw)
                        member_student_id = elem[1]
                        member_name = elem[3]
                        member_email = elem[2]
                        Member.objects.create(user=User.objects.get(username=user_id), student_id = member_student_id, name = member_name, email = member_email)

                        this_year = current_year()
                        try:
                            year = Year.objects.get(year = this_year)
                        except Year.DoesNotExist :
                            year = None

                        if not year:
                            year = Year(year=this_year)
                            year.save()
                            user.userinfo.year = year
                            user.userinfo.sem = current_sem()
                        else:
                            user.userinfo.year = year
                            user.userinfo.sem = current_sem()

                        user.save()


                group_list.clear()
                group_no = data[0]
                group_list.append(data)


        is_first = 1

        for elem in group_list:
            if is_first:
                user_id = "group"+elem[0]
                user_pw = elem[1]
                user_email = elem[2]
                is_first = 0

            if User.objects.filter(username=user_id).exists():
                member_student_id = elem[1]
                member_name = elem[3]
                member_email = elem[2]
                Member.objects.create(user=User.objects.get(username=user_id), student_id = member_student_id, name = member_name, email = member_email)
            else:
                user = User.objects.create_user(username=user_id,
                                    email=user_email,
                                    password=user_pw)
                member_student_id = elem[1]
                member_name = elem[3]
                member_email = elem[2]
                Member.objects.create(user=User.objects.get(username=user_id), student_id = member_student_id, name = member_name, email = member_email)

                this_year = current_year()
                try:
                    year = Year.objects.get(year = this_year)
                except Year.DoesNotExist :
                    year = None

                if not year:
                    year = Year(year=this_year)
                    year.save()
                    user.userinfo.year = year
                    user.userinfo.sem = current_sem()
                else:
                    user.userinfo.year = year
                    user.userinfo.sem = current_sem()

                user.save()

        group_list.clear()

        messages.success(request, '계정들을 성공적으로 생성하였습니다.', extra_tags='alert')
'''
    if username:
        ctx['username'] = username

    return render(request, 'csv_upload.html', ctx)


@csrf_exempt
def export_page(request):
    ctx={}
    if request.user.is_authenticated:
        username = request.user.username
        ctx['username'] = request.user.username
    else:
        return redirect('loginpage')

    if username:
        user = User.objects.get(username=username)
        ctx['userobj'] = user
    else:
        return redirect('loginpage')

    if request.method == 'POST':
        criterion = request.POST['criterion']

        orig_query = 'SELECT username, student_id AS id, name, count_id, count_mem, (count_mem/count_id*100) AS percent FROM photos_member JOIN auth_user ON photos_member.user_id = auth_user.id JOIN (SELECT user_id, COUNT(id) AS count_id FROM photos_data GROUP BY user_id) AS count_data ON photos_member.user_id = count_data.user_id JOIN (SELECT member_id, COUNT(data_id) AS count_mem FROM photos_data_participator JOIN photos_member ON photos_member.id = photos_data_participator.member_id GROUP BY member_id) AS participator ON photos_member.id = participator.member_id WHERE username <> "test" AND count_id >= '

        criterion_str = str(criterion)
        query = orig_query + criterion_str

        member = Data.objects.raw(query)
        response = HttpResponse(content_type = 'text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_final.csv"'

        writer = csv.writer(response, delimiter=',')
        writer.writerow(['group', 'student_id', 'name', '%'])

        for stu in member:
            writer.writerow([stu.username, stu.id, stu.name, stu.percent])

        return response
    else:
        return render(request, 'export_page.html', ctx)

    return render(request, 'export_page.html', ctx)

@csrf_exempt
def export_mile(request):
    ctx={}
    if request.user.is_authenticated:
        username = request.user.username
        ctx['username'] = request.user.username
    else:
        return redirect('loginpage')

    if username:
        user = User.objects.get(username=username)
        ctx['userobj'] = user
    else:
        return redirect('loginpage')

    query = 'SELECT name, student_id AS id, username, count_id, count_mem, sum_study FROM photos_member LEFT JOIN auth_user ON photos_member.user_id = auth_user.id LEFT JOIN (SELECT user_id, COUNT(id) AS count_id FROM photos_data GROUP BY user_id) AS count_data ON photos_member.user_id = count_data.user_id LEFT JOIN (select member_id, count(data_id) AS count_mem, sum(study_total_duration) AS sum_study from photos_data_participator join photos_data on photos_data_participator.data_id = photos_data.id group by member_id) AS participator ON photos_member.id = participator.member_id WHERE username <> "test" ORDER BY username, name'
    member = Data.objects.raw(query)
    response = HttpResponse(content_type = 'text/csv')
    response['Content-Disposition'] = 'attachment; filename="histudy_mileage_list.csv"'

    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=',')
    writer.writerow(['이름', '학번', '그룹번호', '그룹 총 스터디 횟수', '개인별 총 스터디 횟수', '개인별 스터디 참여시간(분)'])

    for stu in member:
        writer.writerow([stu.name, stu.id, stu.username, stu.count_id, stu.count_mem, stu.sum_study])

    return response

def photoList(request, user):
    picList = Data.objects.raw('SELECT * FROM photos_data WHERE author = %s ORDER BY id DESC', [user])
    listuser = user
    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        if user.is_staff is False:
            return redirect('loginpage')
    else:
        return redirect('loginpage')

    ctx = {
        'list' : picList,
        'user' : user,
        'listuser' : listuser,
    }

    if username:
        ctx['username'] = username

    return render(request, 'list.html', ctx)



import datetime
from django.db.models import Q
def userList(request):
    ctx={}
    if request.user.is_authenticated:
        username = request.user.username
        user = request.user
        if user.is_staff is False:
            return redirect('main')
    else:
        return redirect('loginpage')

    ctx['years'] = Year.objects.all()

    if request.method == 'POST':
        year = request.POST['year']
        sem = request.POST['sem']

        if year != 'None' and sem != 'None':
            ctx['chosen_year'] = year
            ctx['chosen_sem'] = sem

    else:
        year = current_year()
        sem = current_sem()
        ctx['year'] = year
        ctx['sem'] = sem

    '''
    userlist = User.objects.filter(Q(is_staff=False) & Q(userinfo__year__year=year) & Q(userinfo__sem=sem)).annotate(
        num_posts = Count('data'),
        recent = Max('data__date'),
        total_dur = Sum('data__study_total_duration'),
    ).exclude(username='test').order_by('-num_posts', 'recent', 'id')


    ctx['list'] = userlist
    ctx['userobj'] = user
    if username:
        ctx['username'] = username
    '''

    return render(request, 'userlist.html', ctx)

def rank(request):
    ctx = {}
    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['user'] = user
        ctx['username'] = username

    year = current_year()
    sem = current_sem()

    userlist = User.objects.filter(Q(is_staff=False) & Q(userinfo__year__year=year) & Q(userinfo__sem=sem)).annotate(
        num_posts = Count('data'),
        recent = Max('data__date'),
        total_dur = Sum('data__study_total_duration'),
    ).exclude(username='test').order_by('-num_posts', 'recent', 'id')

    ctx['list'] = userlist

    return render(request, 'rank.html', ctx)



def top3(request):
    ctx={}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        if user.is_staff is False:
            return redirect('main')
    else:
        return redirect('loginpage')

    ctx['years'] = Year.objects.all()

    if request.method == 'POST':
        year = request.POST['year']
        sem = request.POST['sem']

        if year != 'None' and sem != 'None':
            ctx['chosen_year'] = year
            ctx['chosen_sem'] = sem

    else:
        year = current_year()
        sem = current_sem()
        ctx['year'] = year
        ctx['sem'] = sem


    toplist = User.objects.raw('SELECT id, username, num_posts, date FROM \
                                (SELECT auth_user.id, username, year, sem, \
	                            (SELECT count(*) FROM photos_data WHERE auth_user.username = photos_data.author) AS num_posts, \
	                            (SELECT date FROM photos_data WHERE auth_user.username = photos_data.author AND photos_data.idgroup = 10) AS date \
                                FROM auth_user INNER JOIN photos_userinfo ON auth_user.id = photos_userinfo.user_id INNER JOIN photos_year ON photos_userinfo.year_id = photos_year.id) AS D \
                                WHERE num_posts>9 AND username <> "test" AND year=%s AND sem=%s ORDER BY date LIMIT 3', [year, sem])


    ctx['list'] = toplist
    ctx['userobj'] = user
    if username:
        ctx['username'] = username

    return render(request, 'top3.html', ctx)


def announce(request):
    ctx={}
    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        ctx['username'] = username
    else:
        return redirect('loginpage')

    announceList = Announcement.objects.all()
    ctx['list'] = announceList

    return render(request, 'announce.html', ctx)


def main(request):
    ctx={}

    if request.user.is_authenticated:
        username = request.user.username
        ctx['username'] = username
    else:
        return redirect('loginpage')

    if username:
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        if user.is_staff is True:
            return redirect('userList')
    else:
        return redirect('loginpage')

    dataList = Data.objects.filter(author=user).order_by('-id')

    paginator = Paginator(dataList, 10)
    page = request.GET.get('page', 1)

    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)

    ctx['posts'] = posts
    ctx['userobj'] = user

    return render(request, 'main.html', ctx)

def confirm_delete_data(request, pk):
    ctx={}

    if request.user.is_authenticated:
        loginname = request.user.username
        pass
    else:
        return redirect('loginpage')

    item = Data.objects.get(id=pk)
    username = item.author
    user = User.objects.get(username=username)

    if user.userinfo.num_posts > 0:
        user.userinfo.num_posts -= 1
        user.save()

    Data.objects.filter(id=pk).delete()
    return redirect('main')

def confirm_delete_announce(request, pk):
    ctx={}

    if request.user.is_authenticated:
        loginname = request.user.username
        pass
    else:
        return redirect('loginpage')

    item = Announcement.objects.get(id=pk)
    username = item.author
    user = User.objects.get(username=username)

    Announcement.objects.filter(id=pk).delete()
    messages.success(request, '공지가 삭제되었습니다.', extra_tags='alert')
    return redirect('announce')


# User Login Customization

def trim_string(string1):
    return string1.replace(' ','')

@csrf_exempt
def loginpage(request):
    ctx={}
    if request.method == 'POST':
        username = request.POST['username']
        password =  request.POST['password']

        username = trim_string(username)
        password = trim_string(password)

        user = authenticate(username=username, password=password)

        ctx['user_id'] = username

        if user is not None:
            post = User.objects.filter(username=username)

            if post:
                login(request, user)
                username = request.POST['username']
                response = HttpResponseRedirect(reverse('main'))
                messages.success(request, '환영합니다.', extra_tags='alert')
                return response
            else:
                messages.warning(request, '다시 로그인 해주세요.', extra_tags='alert')
                return render(request, 'login.html', ctx)
        else:
            messages.warning(request, '다시 로그인 해주세요.', extra_tags='alert')

    return render(request, 'login.html', ctx)

def group_profile(request, user):
    memuser = User.objects.get(username=user)
    ctx={}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['user'] = user
        if user.is_staff is False:
            return redirect('loginpage')
    else:
        return redirect('loginpage')

    if username:
        ctx['username'] = username

    memberList = Member.objects.filter(user=memuser).annotate(
        num_posts = Count('data'),
        total_time = Sum('data__study_total_duration')
    )
    ctx['list'] = memberList

    return render(request, 'group_profile.html', ctx)


@login_required(login_url=LOGIN_REDIRECT_URL)
def profile(request):
    ctx={}

    # Tag.objects.filter(person__yourcriterahere=whatever [, morecriteria]).annotate(cnt=Count('person')).order_by('-cnt')[0]
    yearobj = Year.objects.all()[0]
    try:
        user = User.objects.get(pk=request.user.pk)

        # member_list annotate으로 num_posts, total_time 구해야되는데, data model이 없다고 뜸 ㅠ
        member_list = User.objects.filter(profile__group=user.profile.group).annotate(
            num_posts = Count('data', filter=Q(data__year=yearobj)),
            total_time = Sum('data__study_total_duration', filter=Q(data__year=yearobj))
        )

        ctx['member_list'] = member_list
    except User.DoesNotExist:
        return redirect(reverse('loginpage'))

    return render(request, 'profile.html', ctx)

@login_required(login_url=LOGIN_REDIRECT_URL)
def staff_profile(request):
    ctx={}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
    else:
        return redirect('loginpage')

    if username:
        ctx['username'] = username

    return render(request, 'staff_profile.html', ctx)

@login_required(login_url=LOGIN_REDIRECT_URL)
def grid(request):
    ctx = {}
    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        if user.is_staff is False:
            return redirect('main')
    else:
        return redirect('loginpage')

    if username:
        ctx['username'] = username

    ctx['years'] = Year.objects.all()

    if request.method == 'POST':
        year = request.POST['year']
        sem = request.POST['sem']

        if year != 'None' and sem != 'None':
            ctx['chosen_year'] = year
            ctx['chosen_sem'] = sem

    else:
        year = current_year()
        sem = current_sem()
        ctx['year'] = year
        ctx['sem'] = sem


    ctx['data'] = Data.objects.raw('SELECT * FROM photos_data INNER JOIN \
        (SELECT MAX(id) as id FROM photos_data GROUP BY author) \
            last_updates ON last_updates.id = photos_data.id INNER JOIN photos_userinfo ON photos_data.user_id = photos_userinfo.user_id INNER JOIN photos_year ON photos_userinfo.year_id = photos_year.id\
                WHERE author <> "kate" AND author <> "test" AND author IS NOT NULL AND year=%s AND sem =%s ORDER BY date DESC', [year, sem])

    return render(request, 'grid.html', ctx)

def logout_view(request):
    try:
        logout(request)
        response = HttpResponseRedirect(reverse('loginpage'))
        return response
    except:
        pass
    return render(request, 'home.html', {})


def signup(request):
    ctx = {}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        if user.is_staff is False:
            return redirect('main')
    else:
        return redirect('loginpage')

    ctx['username'] = username
    if request.method == 'POST':
        if request.POST["password1"] == request.POST["password2"]:
            user = User.objects.create_user(
                username=request.POST["username"],
                password=request.POST["password1"]
            )

            this_year = current_year()
            try:
                year = Year.objects.get(year = this_year)
            except Year.DoesNotExist :
                year = None

            if not year:
                year = Year(year=this_year)
                year.save()
                user.userinfo.year = year
                user.userinfo.sem = current_sem()
            else:
                user.userinfo.year = year
                user.userinfo.sem = current_sem()

            user.save()
            messages.success(request, '유저가 성공적으로 추가되었습니다.', extra_tags='alert')
            return redirect("staff_profile")

        else:
            messages.warning(request, '유저를 만드는데 실패하였습니다.', extra_tags='alert')
        return render(request, 'signup.html', ctx)

    return render(request, 'signup.html', ctx)


@login_required(login_url=LOGIN_REDIRECT_URL)
@transaction.atomic
def save_profile(request, pk):
    user = User.objects.get(pk=pk)

    if user.profile.phone and user.profile.student_id:
        return redirect(reverse('main'))

    if request.method == 'POST':
        profile = user.profile
        student_id = StudentID.objects.get(student_id=request.POST['student_id'])
        profile.student_id = student_id
        profile.phone = "010" + str(request.POST['phone1']) + str(request.POST['phone2'])
        profile.save()
        return redirect(reverse('main'))

    return render(request, 'save_profile.html')



# UserInfo가 없을 때 관리자에게 문의하는 곳
@login_required(login_url=LOGIN_REDIRECT_URL)
@transaction.atomic
def create_userinfo(request, pk):
    messages.info(request, '학우님의 정보가 DB에 없습니다. 관리자에게 문의해주세요')

    try:
        user = User.objects.get(pk=pk)
    except:
        return redirect(reverse('loginpage'))

    if request.method == 'POST':
        student_id = request.POST['student_id']
        email = request.POST['email']
        print(student_id)
        print(email)

    return render(request, 'create_userinfo.html')


def user_check(request):
    if request.user.email.endswith('@handong.edu'):
        try:
            user = User.objects.get(pk=request.user.pk)
            user.email = request.user.email

            # 학교 이메일이 학번으로 시작한다고 가정
            std_id = user.username
            username = user.last_name
            email = user.email


            try:
                student_id = StudentID.objects.get(student_id=std_id)
            except StudentID.DoesNotExist:
                student_id = StudentID.objects.create(student_id=std_id)

            try:
                user_info = UserInfo.objects.get(student_id=student_id)
            except UserInfo.DoesNotExist:
                # user info 가 저장안된 유저는 문의 페이지로! (profile아직 생성안됨)
                return redirect(reverse('create_userinfo', args=(user.pk,)))

            try:
                user_profile = user.profile
            except Profile.DoesNotExist:
                user_profile = Profile.objects.create(user=user, name=username, email=email)
                if user_info:
                    user_profile.group = user_info.group

                user_profile.save()
                return HttpResponseRedirect(reverse('save_profile', args=(user.pk,)))

        except(KeyError, User.DoesNotExist):
            return HttpResponseRedirect(reverse('loginpage'))
    else:
        messages.info(request, '한동 이메일로 로그인해주세요.')
        User.objects.filter(pk=request.user.pk).delete()
        return HttpResponseRedirect(reverse('loginpage'))


def announce_write(request):
    ctx = {}
    if request.user.is_authenticated:
        username = request.user.username
        ctx['username'] = username
        user = User.objects.get(username = username)
        ctx['userobj'] = user
        if user.is_staff is False:
            return redirect('announce')
    else:
        return redirect('loginpage')

    if request.method == "GET":
        form = AnnouncementForm()
    elif request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            obj.author = username
            obj.save()
            messages.success(request, '공지가 추가되었습니다.', extra_tags='alert')
            return redirect("announce")

    ctx['form'] = form

    return render(request, 'announce_write.html', ctx)

def announce_detail(request, pk):
    post = get_object_or_404(Announcement, pk=pk)

    ctx = {
        'post': post,
    }

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username = username)
        ctx['userobj'] = user
        ctx['username'] = username
    else:
        return redirect('loginpage')

    return render(request, 'announce_content.html', ctx)


def change_password(request):
    ctx = {}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
    else:
        return redirect('loginpage')

    ctx['username'] = username
    if request.method == 'POST':
        old_password = request.POST["old_password"]
        is_pw_correct = authenticate(username=username, password=old_password)
        if is_pw_correct is not None:
            password1 = request.POST["password1"]
            password2 = request.POST["password2"]

            if password1 == password2:
                user.set_password(password1)
                user.save()
                messages.success(request, '비밀번호가 변경 되었습니다.', extra_tags='alert')
                login(request, user)
                return redirect("profile")

            else:
                messages.warning(request, '바꾸는 비밀번호가 일치해야합니다.', extra_tags='alert')

            return redirect("change_password")
        else:
            messages.warning(request, '현재 비밀번호를 확인해주세요.', extra_tags='alert')
            return render(request, 'change_password.html', ctx)

    return render(request, 'change_password.html', ctx)


def add_member(request):
    ctx={}

    if request.user.is_authenticated:
        username = request.user.username
        ctx['username'] = username
    else:
        return redirect('loginpage')

    if username:
        user = User.objects.get(username=username)
        ctx['userobj'] = user

    if request.method == "GET":
        form = MemberForm()
    elif request.method == "POST":
        form = MemberForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            obj.author = username
            obj.user = user
            obj.save()
            messages.success(request, '멤버가 추가되었습니다.', extra_tags='alert')
            return redirect("profile")
        else:
            messages.warning(request, '학번을 확인해주세요.', extra_tags='alert')

    ctx['form'] = form

    return render(request, 'member.html', ctx)

def confirm_delete_member(request, pk):
    item = Member.objects.get(id=pk)
    Member.objects.filter(id=pk).delete()
    return redirect('profile')


def confirm_delete_user(request, pk):
    user = User.objects.get(id=pk)
    User.objects.filter(id=pk).delete()
    return redirect('userList')


# For verification popup
def popup(request):
    ctx = {}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        orig, created = Verification.objects.get_or_create(user=user)

        now_time = timezone.localtime()


        if user.verification.code_when_saved is None:
            user.verification.code_when_saved = now_time
            verify_code = random.choice(possible)
            user.verification.code = verify_code
            user.save()
            ctx['code'] = verify_code


        save_time = user.verification.code_when_saved

        time_diff = now_time - save_time

        if (time_diff.seconds)/60 >= 10:
            verify_code = random.choice(possible)
            user.verification.code = verify_code
            user.verification.code_when_saved = now_time
            user.save()
            ctx['code'] = verify_code
        else:
            if user.verification.code is None:
                verify_code = random.choice(possible)
                user.verification.code = verify_code
                user.verification.code_when_saved = now_time
                user.save()
                ctx['code'] = verify_code
            else:
                ctx['code'] = user.verification.code

        return render(request, 'popup.html', ctx)
    else:
        return redirect("main")

def inquiry(request):
    ctx = {}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        ctx['username'] = username

    return render(request, 'inquiry.html', ctx)


def img_download_page(request):
    ctx={}

    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        if user.is_staff is False:
            return redirect('main')
    else:
        return redirect('loginpage')

    years = Year.objects.all()
    ctx['years'] = years

    if request.method == 'POST':
        year = request.POST['year']
        sem = request.POST['sem']

        if year != 'None' and sem != 'None':
            ctx['chosen_year'] = year
            ctx['chosen_sem'] = sem

            year_obj = Year.objects.get(year=year)
            return redirect('img_download', year_obj.pk)

    else:
        year = current_year()
        sem = current_sem()
        ctx['year'] = year
        ctx['sem'] = sem

    return render(request, 'img_download_page.html', ctx)

from django.conf import settings
import zipfile
from wsgiref.util import FileWrapper
import os

def img_download(request, pk):
    home = os.path.expanduser('~')
    location = os.path.join(home, 'Downloads')
    location += '/'

    ctx={}
    if request.user.is_authenticated:
        username = request.user.username
        user = User.objects.get(username=username)
        ctx['userobj'] = user
        if user.is_staff is False:
            return redirect('main')
    else:
        return redirect('loginpage')


    year = Year.objects.get(pk=pk)
    user_list = User.objects.filter(userinfo__year=year)

    export_zip = zipfile.ZipFile("/home/chickadee/projects/HGUstudy/histudy_img.zip", 'w')

    for user in user_list:
        cnt=1
        if not user.is_staff:
            # print(">>> User: " + user.username)
            image_list = Data.objects.raw('SELECT * FROM photos_data WHERE user_id = %s', [user.pk])

            for image in image_list:
                file_name = user.username + '_' + str(cnt) + '.png'
                product_image_url = image.image.url

                image_path = settings.MEDIA_ROOT+ product_image_url[13:]
                image_name = product_image_url; # Get your file name here.

                export_zip.write(image_path, file_name)
                cnt += 1

    export_zip.close()

    wrapper = FileWrapper(open('/home/chickadee/projects/HGUstudy/histudy_img.zip', 'rb'))
    content_type = 'application/zip'
    content_disposition = 'attachment; filename=histudy_img.zip'

    response = HttpResponse(wrapper, content_type=content_type)
    response['Content-Disposition'] = content_disposition


    return response
